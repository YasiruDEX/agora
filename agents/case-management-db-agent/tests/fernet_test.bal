// Fernet tests.
//
// The interop vectors below matter more than the round-trip tests: a self-consistent
// encrypt/decrypt pair proves nothing about wire compatibility, and wire compatibility with
// Python's `cryptography.fernet` is the whole reason fernet.bal exists rather than some
// simpler Ballerina-only scheme. These four tokens were produced by Python:
//
//   from cryptography.fernet import Fernet
//   Fernet(b"V1KMEbNn7hbwsUyoIWzk3fRlZeMxaBLGyQCbdWLmYnE=").encrypt(b"hello")
//
// so if the AES/HMAC/base64url handling in fernet.bal ever drifts, these fail. The key is a
// throwaway test fixture; tests/Config.toml and test.sh pin it as CASEMGMT_ENCRYPTION_KEY so
// `fernetKey` is derived from it.
import ballerina/test;

const string PY_TOKEN_SHORT = "gAAAAABqmrvVUDVxKYS2Eb6sIHOyFJmGYLZrUJBpOjVA-ytlJ4wDjnZhwM0vajv0_I_LxdTnQF9v7cclvsWLkD9RZNTOcCrXTg==";
const string PY_TOKEN_UNICODE = "gAAAAABqmrvVyZREom20gcvCi7XZaDEFZ1i7DKAmJ-u0yc7rTb8mEQ4fgmciEStaYkGxcMbJbCEBS3sTky9mg15pvGUTiBCMVJ0btEnhNWo99TrYCr1iM64=";
const string PY_TOKEN_LONG = "gAAAAABqmrvVUyIGKlwHYTV-gSV97g64f642DYY2G3GvLKzc0AEvNqu5xyB-JzOl02iITz_RRQYg4d9QYQ-0Gyrp-GF5WGLCesZ0p4ozTWKaRSgBJq_8_P4_30vn8xTgSZ13OGYVr-Wn74iSLRdjJrFLg5E-OJ-y1SPRx-paHz7vupklbBZrih3JvFH7X-ThLRdOX75b24OO_mi1ZVLyUUvT9iurtHAjNDvL4BZr0OydiSfDU1Los98hEogiNw2lBJ9V3j8AfxBxKhdjb-GivXr1uh34N4fP_Krj60R710NKJh1Zppjfm-xi7La-2dAjWaKd-ACH6ah18CPSmSWKyUlXz0rlShMvATLe_Wzr2Zp5T8tptKWxxXzF7jXJogKrI_bJuiwhr1A8KIPI4jrdVbqlY10NqO2vngf3i3649OTVIaTavSD_B54=";
const string PY_TOKEN_EMPTY = "gAAAAABqmrvVMNKsMjqY97newbN4EbybENYkotY493q6RMS-LEi3VGmrDa5k_4eZoAm-D-aJEbOC_JiHN8qF8NDET9d9Ipfwow==";

@test:Config {groups: ["fernet", "interop"]}
function testDecryptsPythonToken() returns error? {
    test:assertEquals(check fernetDecrypt(PY_TOKEN_SHORT), "hello");
}

@test:Config {groups: ["fernet", "interop"]}
function testDecryptsPythonTokenWithMultibyteCharacters() returns error? {
    // Guards the toBytes()/fromBytes() boundary: Fernet encrypts UTF-8 bytes, so an accent
    // or an em dash must survive without being re-encoded.
    test:assertEquals(check fernetDecrypt(PY_TOKEN_UNICODE), "Renée — 62 hours/month ✓");
}

@test:Config {groups: ["fernet", "interop"]}
function testDecryptsMultiBlockPythonToken() returns error? {
    // Long enough to span many AES blocks, so a padding or slicing error shows up here even
    // when the single-block case passes.
    string decrypted = check fernetDecrypt(PY_TOKEN_LONG);
    test:assertTrue(decrypted.startsWith("Home visit completed."));
    test:assertEquals(decrypted.length(), ("Home visit completed. ".length() * 12) - 1);
}

@test:Config {groups: ["fernet", "interop"]}
function testDecryptsEmptyPlaintextPythonToken() returns error? {
    // An empty string still produces one full block of PKCS7 padding — the case most likely
    // to be mishandled.
    test:assertEquals(check fernetDecrypt(PY_TOKEN_EMPTY), "");
}

@test:Config {groups: ["fernet"]}
function testRoundTrip() returns error? {
    string[] samples = [
        "hello",
        "",
        "Renée — 62 hours/month ✓",
        "Home visit completed. Needs assessment scored at 62 hours/month pending supervisor sign-off.",
        "exactly-sixteen"
    ];
    foreach string sample in samples {
        string token = check fernetEncrypt(sample);
        test:assertEquals(check fernetDecrypt(token), sample,
                string `round trip failed for '${sample}'`);
    }
}

@test:Config {groups: ["fernet"]}
function testEncryptIsNonDeterministic() returns error? {
    // A fresh random IV per call, so identical notes don't produce identical ciphertext —
    // otherwise the store would leak which notes match each other.
    string a = check fernetEncrypt("same plaintext");
    string b = check fernetEncrypt("same plaintext");
    test:assertNotEquals(a, b);
    test:assertEquals(check fernetDecrypt(a), check fernetDecrypt(b));
}

@test:Config {groups: ["fernet"]}
function testTokensAreBase64UrlAndVersioned() returns error? {
    string token = check fernetEncrypt("hello");
    test:assertTrue(token.startsWith("gAAAAA"),
            "a v0x80 Fernet token always begins with the 0x80 version byte");
    test:assertFalse(token.includes("+"), "base64url must not contain '+'");
    test:assertFalse(token.includes("/"), "base64url must not contain '/'");
}

@test:Config {groups: ["fernet"]}
function testRejectsTamperedCiphertext() returns error? {
    // The HMAC is checked before the cipher runs, so flipping a ciphertext character must be
    // refused rather than yielding garbage plaintext.
    string token = check fernetEncrypt("Supervisor signed off on 62 authorized hours/month.");
    int flipAt = token.length() - 40;
    string:Char original = <string:Char>token[flipAt];
    string tampered = token.substring(0, flipAt) + (original == "A" ? "B" : "A") +
            token.substring(flipAt + 1);

    string|error result = fernetDecrypt(tampered);
    test:assertTrue(result is error, "a tampered token must not decrypt");
    if result is error {
        test:assertTrue(result.message().includes("HMAC mismatch"),
                string `expected an HMAC failure, got: ${result.message()}`);
    }
}

@test:Config {groups: ["fernet"]}
function testRejectsMalformedTokens() {
    // Every one of these is something a corrupted or wrong-key database column could contain,
    // and each must produce an error rather than a panic — listNotes() turns the error into a
    // per-note placeholder, so a single bad row can't take down a whole case read.
    string[] malformed = ["", "not-a-token", "gAAAAA", "!!!not base64!!!"];
    foreach string candidate in malformed {
        string|error result = fernetDecrypt(candidate);
        test:assertTrue(result is error, string `expected '${candidate}' to be rejected`);
    }
}

@test:Config {groups: ["fernet"]}
function testRejectsUnsupportedVersionByte() returns error? {
    // Same key, same structure, wrong version byte (0x81) — must be refused on the version
    // check, before the HMAC is even considered.
    byte[] raw = check fromBase64Url(check fernetEncrypt("hello"));
    raw[0] = 0x81;
    string|error result = fernetDecrypt(toBase64Url(raw));
    test:assertTrue(result is error);
    if result is error {
        test:assertTrue(result.message().includes("Unsupported Fernet version"),
                string `expected a version error, got: ${result.message()}`);
    }
}

@test:Config {groups: ["fernet"]}
function testRejectsWrongLengthKey() {
    string[] badKeys = ["", "c2hvcnQ=", "V1KMEbNn7hbwsUyoIWzk3fRlZeMxaBLGyQCbdWLmYnE=extra"];
    foreach string candidate in badKeys {
        FernetKey|error parsed = parseFernetKey(candidate);
        test:assertTrue(parsed is error, string `expected key '${candidate}' to be rejected`);
    }
}

@test:Config {groups: ["fernet"]}
function testKeyIsSplitIntoSigningAndEncryptionHalves() returns error? {
    FernetKey key = check parseFernetKey("V1KMEbNn7hbwsUyoIWzk3fRlZeMxaBLGyQCbdWLmYnE=");
    test:assertEquals(key.signingKey.length(), 16);
    test:assertEquals(key.encryptionKey.length(), 16);
    test:assertNotEquals(key.signingKey, key.encryptionKey);
}

@test:Config {groups: ["fernet"]}
function testBase64UrlTranslationRoundTrips() returns error? {
    // The codec is standard base64 with two characters swapped, so the swap has to be exactly
    // symmetric — an asymmetric mapping would corrupt roughly one token in sixty-four.
    byte[] payload = [];
    foreach int i in 0 ..< 256 {
        payload.push(<byte>i);
    }
    test:assertEquals(check fromBase64Url(toBase64Url(payload)), payload);
}

@test:Config {groups: ["fernet"]}
function testInt64BigEndianEncoding() {
    test:assertEquals(int64BigEndian(0), <byte[]>[0, 0, 0, 0, 0, 0, 0, 0]);
    test:assertEquals(int64BigEndian(1), <byte[]>[0, 0, 0, 0, 0, 0, 0, 1]);
    test:assertEquals(int64BigEndian(256), <byte[]>[0, 0, 0, 0, 0, 0, 1, 0]);
    test:assertEquals(int64BigEndian(0x0102030405060708), <byte[]>[1, 2, 3, 4, 5, 6, 7, 8]);
}

@test:Config {groups: ["fernet", "interop"]}
function testTimestampFieldMatchesPythonsLayout() returns error? {
    // Verified against a real Python token instead of a hardcoded number: read the 8 bytes
    // Python wrote at offset 1, decode them big-endian, and check int64BigEndian reproduces
    // them exactly. A wrong width, offset, or byte order fails here.
    byte[] raw = check fromBase64Url(PY_TOKEN_SHORT);
    byte[] pythonTimestamp = raw.slice(1, 9);

    int recovered = 0;
    foreach byte b in pythonTimestamp {
        recovered = (recovered << 8) | b;
    }
    test:assertEquals(int64BigEndian(recovered), pythonTimestamp);
    // Sanity-check it really is a plausible epoch second rather than a coincidence: after
    // 2020 and before 2100.
    test:assertTrue(recovered > 1577836800 && recovered < 4102444800,
            string `${recovered} is not a plausible epoch timestamp`);
}

@test:Config {groups: ["fernet"]}
function testConstantTimeEquals() {
    test:assertTrue(constantTimeEquals([1, 2, 3], [1, 2, 3]));
    test:assertFalse(constantTimeEquals([1, 2, 3], [1, 2, 4]));
    test:assertFalse(constantTimeEquals([1, 2, 3], [1, 2]));
    test:assertTrue(constantTimeEquals([], []));
}

@test:Config {groups: ["fernet"]}
function testRandomBytesLengthAndVariety() returns error? {
    byte[] a = check randomBytes(16);
    byte[] b = check randomBytes(16);
    test:assertEquals(a.length(), 16);
    test:assertEquals(b.length(), 16);
    test:assertNotEquals(a, b, "two 16-byte draws colliding means the IV source is broken");
}
