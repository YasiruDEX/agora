import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { LANGUAGES, translate } from './translations'

const LanguageContext = createContext(null)

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem('gov_lang') || 'en')

  useEffect(() => {
    localStorage.setItem('gov_lang', lang)
    document.documentElement.lang = lang
  }, [lang])

  const value = useMemo(
    () => ({
      lang,
      setLang,
      languages: LANGUAGES,
      t: (path) => translate(lang, path),
    }),
    [lang],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within a LanguageProvider')
  return ctx
}
