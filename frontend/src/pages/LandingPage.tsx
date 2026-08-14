import { Link } from 'react-router-dom'
import { Card } from '../components/ui'

const FEATURES = [
  {
    title: 'Blockchain Trust Ledger',
    body: 'Seller trust scores recorded as immutable on-chain events (TrustScore.sol) — tampering with history breaks the chain.',
  },
  {
    title: 'AI Fraud Detection',
    body: 'Every order is scored in real time by a trained classifier (90%+ accuracy) before it settles, with explainable risk factors.',
  },
  {
    title: 'Hybrid Recommendations',
    body: 'Content-based, collaborative, and popularity-based matching blended with live seller trust — with real measured CTR.',
  },
  {
    title: 'Automated Disputes',
    body: 'Evidence-weighted resolution using both parties’ trust scores, mirroring the on-chain escrow contract’s own rules.',
  },
]

export function LandingPage() {
  return (
    <div>
      <section className="mx-auto max-w-5xl px-4 py-20 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-brand-navy sm:text-5xl dark:text-white">
          Blockchain-AI Enhanced <span className="text-brand-blue">ONDC</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-600 dark:text-slate-300">
          A decentralized trust and fraud-detection layer for open digital commerce — buyer and seller
          registration, on-chain trust scoring, AI fraud detection, and automated dispute resolution, backed by
          real smart contracts.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            to="/signup"
            className="rounded-lg bg-brand-blue px-6 py-3 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Get started
          </Link>
          <Link
            to="/login"
            className="rounded-lg border border-slate-300 px-6 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-900"
          >
            Log in
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 pb-20">
        <div className="grid gap-4 sm:grid-cols-2">
          {FEATURES.map((feature) => (
            <Card key={feature.title} className="p-6">
              <h2 className="font-semibold">{feature.title}</h2>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{feature.body}</p>
            </Card>
          ))}
        </div>
      </section>
    </div>
  )
}
