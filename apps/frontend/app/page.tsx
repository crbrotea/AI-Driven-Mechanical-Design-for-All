import { FooterCTA } from '@/components/landing/FooterCTA'
import { Hero } from '@/components/landing/Hero'
import { HeroDemos } from '@/components/landing/HeroDemos'
import { PipelineStrip } from '@/components/landing/PipelineStrip'
import { ProofStrip } from '@/components/landing/ProofStrip'
import { Topbar } from '@/components/shared/Topbar'

export default function Landing() {
  return (
    <>
      <Topbar />
      <main>
        <Hero />
        <PipelineStrip />
        <HeroDemos />
        <ProofStrip />
        <FooterCTA />
      </main>
    </>
  )
}
