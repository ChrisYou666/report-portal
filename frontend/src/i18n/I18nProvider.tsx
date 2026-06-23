import { createContext, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { id } from './locales/id'
import { zh } from './locales/zh'
import type { I18nMessages, Language } from './types'

const messages: Record<Language, I18nMessages> = {
  zh,
  id,
}

type I18nContextValue = {
  language: Language
  setLanguage: (language: Language) => void
  toggleLanguage: () => void
  t: I18nMessages
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>('zh')

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage,
      toggleLanguage: () => setLanguage((current) => (current === 'zh' ? 'id' : 'zh')),
      t: messages[language],
    }),
    [language],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used inside I18nProvider')
  }
  return context
}
