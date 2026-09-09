// Fernet (spec version 0x80) encrypt/decrypt, wire-compatible with Python's
// `cryptography.fernet.Fernet`.
//
// Why implement it rather than store plaintext: the case store's citizen PII (name, DOB, SSN
// last 4, address, phone, email) and case-note content are encrypted at rest, and this agent
// now owns that store directly. Matching Fernet exactly — rather than inventing a Ballerina
// -only scheme — means this agent and the MCP twin
// (../../mcp-servers/case-management-mcp-server) can read and write the *same* database file
// with the same key. A note this agent writes is readable by the Python server and vice
// versa, which is what lets the two be swapped without a data migration.
//
// Token layout (all one base64url blob, padding included, exactly as Python emits it):
//
//   ┌─────────┬──────────────────┬──────────┬────────────────┬──────────────────┐
//   │ 0x80    │ timestamp        │ IV       │ ciphertext     │ HMAC-SHA256      │
//   │ 1 byte  │ 8 bytes, big-end │ 16 bytes │ 16*n bytes     │ 32 bytes         │
//   └─────────┴──────────────────┴──────────┴────────────────┴──────────────────┘
//
//   ciphertext = AES-128-CBC(PKCS7) over the plaintext, under the key's second 16 bytes
//   HMAC       = HMAC-SHA256 over version|timestamp|IV|ciphertext, under the first 16 bytes
//
// Deliberately *not* implemented: Fernet's optional TTL check on the embedded timestamp.
// Python's store doesn't pass a ttl either, so enforcing one here would reject rows the MCP
// twin considers valid. The timestamp is still written correctly so a future reader can use
// it.
import ballerina/crypto;
import ballerina/lang.array;
import ballerina/random;
import ballerina/time;

const byte FERNET_VERSION = 0x80;
const int FERNET_KEY_BYTES = 32;
const int FERNET_IV_BYTES = 16;
const int FERNET_HMAC_BYTES = 32;
// version(1) + timestamp(8) + IV(16) + at least one AES block(16) + HMAC(32)
const int FERNET_MIN_TOKEN_BYTES = 73;

type FernetKey record {|
    byte[] signingKey;
    byte[] encryptionKey;
|};

final readonly & FernetKey fernetKey = check parseFernetKey(encryptionKeyB64);

isolated function parseFernetKey(string keyB64Url) returns (readonly & FernetKey)|error {
    byte[] raw = check fromBase64Url(keyB64Url.trim());
    if raw.length() != FERNET_KEY_BYTES {
        return error(string `Invalid CASEMGMT_ENCRYPTION_KEY: expected a base64url-encoded ` +
                    string `${FERNET_KEY_BYTES}-byte Fernet key, decoded to ${raw.length()} bytes`);
    }
    // Fernet splits the 32-byte key: first half signs, second half encrypts. Returned
    // readonly so the isolated request path can read it without a lock.
    FernetKey key = {signingKey: raw.slice(0, 16), encryptionKey: raw.slice(16, FERNET_KEY_BYTES)};
    return <readonly & FernetKey>key.cloneReadOnly();
}

isolated function fernetEncrypt(string plaintext) returns string|error {
    byte[] iv = check randomBytes(FERNET_IV_BYTES);
    byte[] ciphertext = check crypto:encryptAesCbc(plaintext.toBytes(), fernetKey.encryptionKey, iv);

    byte[] signed = [FERNET_VERSION];
    signed.push(...int64BigEndian(time:utcNow()[0]));
    signed.push(...iv);
    signed.push(...ciphertext);

    byte[] mac = check crypto:hmacSha256(signed, fernetKey.signingKey);
    byte[] token = [...signed];
    token.push(...mac);
    return toBase64Url(token);
}

isolated function fernetDecrypt(string token) returns string|error {
    byte[] raw = check fromBase64Url(token.trim());
    if raw.length() < FERNET_MIN_TOKEN_BYTES {
        return error(string `Malformed Fernet token: ${raw.length()} bytes, minimum is ${FERNET_MIN_TOKEN_BYTES}`);
    }
    if raw[0] != FERNET_VERSION {
        return error(string `Unsupported Fernet version 0x${raw[0].toHexString()}`);
    }

    int macStart = raw.length() - FERNET_HMAC_BYTES;
    byte[] signed = raw.slice(0, macStart);
    byte[] presentedMac = raw.slice(macStart, raw.length());
    byte[] expectedMac = check crypto:hmacSha256(signed, fernetKey.signingKey);
    if !constantTimeEquals(presentedMac, expectedMac) {
        // Authenticate before decrypting, as the spec requires — never feed unverified bytes
        // to the cipher. In practice this fires when the key is wrong for the database.
        return error("Fernet HMAC mismatch — CASEMGMT_ENCRYPTION_KEY does not match this database");
    }

    byte[] iv = raw.slice(9, 9 + FERNET_IV_BYTES);
    byte[] ciphertext = raw.slice(9 + FERNET_IV_BYTES, macStart);
    byte[] plaintext = check crypto:decryptAesCbc(ciphertext, fernetKey.encryptionKey, iv);
    return string:fromBytes(plaintext);
}

// Compare in time independent of where the first difference falls, so a mismatching MAC
// can't be probed byte by byte.
isolated function constantTimeEquals(byte[] a, byte[] b) returns boolean {
    if a.length() != b.length() {
        return false;
    }
    int diff = 0;
    foreach int i in 0 ..< a.length() {
        diff |= a[i] ^ b[i];
    }
    return diff == 0;
}

isolated function int64BigEndian(int value) returns byte[] {
    byte[] out = [];
    foreach int i in 0 ..< 8 {
        out.push(<byte>((value >> ((7 - i) * 8)) & 0xFF));
    }
    return out;
}

isolated function randomBytes(int count) returns byte[]|error {
    byte[] out = [];
    foreach int _ in 0 ..< count {
        // random:createIntInRange is exclusive of the upper bound.
        out.push(<byte>(check random:createIntInRange(0, 256)));
    }
    return out;
}

// Fernet uses base64url *with* '=' padding, which is exactly standard base64 with two
// characters substituted — so translate rather than reimplement the codec.
isolated function toBase64Url(byte[] data) returns string => translateBase64(data.toBase64(), true);

isolated function fromBase64Url(string encoded) returns byte[]|error => array:fromBase64(translateBase64(encoded, false));

isolated function translateBase64(string value, boolean toUrlSafe) returns string {
    string:Char plusChar = toUrlSafe ? "+" : "-";
    string:Char slashChar = toUrlSafe ? "/" : "_";
    string:Char plusRepl = toUrlSafe ? "-" : "+";
    string:Char slashRepl = toUrlSafe ? "_" : "/";

    string out = "";
    foreach string:Char ch in value {
        if ch == plusChar {
            out += plusRepl;
        } else if ch == slashChar {
            out += slashRepl;
        } else {
            out += ch;
        }
    }
    return out;
}
