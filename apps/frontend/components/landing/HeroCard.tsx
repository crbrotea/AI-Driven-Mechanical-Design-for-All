import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { Card } from '@/components/ui/card'

export function HeroCard({ preset }: { preset: 'flywheel' | 'hydro' | 'shelter' }) {
  const t = useTranslations('landing.heroes')
  return (
    <Link href={`/design?preset=${preset}`} className="block">
      <Card className="p-6 transition hover:shadow-md">
        <h3 className="text-lg font-semibold">{t(`${preset}.title`)}</h3>
        <p className="mt-2 text-sm text-muted-foreground">{t(`${preset}.subtitle`)}</p>
      </Card>
    </Link>
  )
}
