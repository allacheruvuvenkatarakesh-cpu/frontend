import { motion } from 'framer-motion'
import { ArrowRight, AudioLines, Clock, FileDown, FileSearch, Fingerprint, Languages, Link2, ListChecks, Network, Quote, Scale, ScanFace, ShieldCheck, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button, Logo } from '../components/ui/index.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const fade = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } }

const STEPS = [
  { icon: Link2, title: 'Capture', text: 'Paste a link from a supported platform or upload a video file.' },
  { icon: AudioLines, title: 'Understand', text: 'Whisper transcribes the speech; an LLM pulls out checkable claims with timestamps.' },
  { icon: FileSearch, title: 'Verify', text: 'Each claim is checked against retrieved evidence from trusted sources.' },
  { icon: ListChecks, title: 'Show', text: 'Verdicts, sources and a colour-coded truth timeline you can click through.' },
]

const FEATURES = [
  { icon: Scale, title: 'Evidence first', text: 'Every verdict links to the passages it rests on. No evidence, no verdict: claims are marked "Insufficient Evidence" instead of guessed.' },
  { icon: Clock, title: 'Timestamped', text: 'Jump straight to the second a claim was made and hear it in context.' },
  { icon: ShieldCheck, title: 'Honest confidence', text: 'Confidence is computed from how much credible, independent evidence agrees, not from the AI’s self-assessment.' },
  { icon: Upload, title: 'Any video', text: 'YouTube, Vimeo and other public links, direct media URLs, or your own uploads.' },
]

const INNOVATIONS = [
  { icon: Fingerprint, title: 'Truth Fingerprint', text: 'A unique, versioned credibility record for every video, comparable across videos.' },
  { icon: Languages, title: 'Telugu · Hindi · English', text: 'Claims kept in the speaker\u2019s words, translated for searching, results in your language.' },
  { icon: ScanFace, title: 'Media authenticity', text: 'Signal checks for splices, timing gaps and lip-sync problems, with honest uncertainty.' },
  { icon: Quote, title: 'Context detector', text: 'Flags quotes taken out of context, misleading statistics and self-contradictions.' },
  { icon: ShieldCheck, title: 'Source trust analyser', text: 'Publisher, author, date, primary source and corroboration, never reputation alone.' },
  { icon: Network, title: 'Evidence graph', text: 'See how claims, sources and related videos connect, at a glance.' },
  { icon: FileDown, title: 'PDF fact-check report', text: 'A shareable report with verdicts, evidence, fingerprint and limitations.' },
]
const STACK = ['React + Vite', 'Tailwind CSS', 'Framer Motion', 'Recharts', 'React Flow', 'FastAPI', 'MongoDB', 'Whisper',
  'OpenAI-compatible LLM', 'Sentence Transformers', 'ChromaDB', 'FFmpeg', 'OpenCV', 'ReportLab', 'Docker']

const DEMO_TIMELINE = [
  ['verified', 12], ['unverified', 6], ['false', 10], ['verified', 14], ['misleading', 9], ['verified', 8], ['false', 7],
]
const COLORS = { verified: '#16a34a', false: '#dc2626', misleading: '#eab308', unverified: '#9ca3af' }

export default function LandingPage() {
  const { user } = useAuth()
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Logo />
        <nav className="flex items-center gap-2">
          {user ? (
            <Button as={Link} to="/dashboard">Open dashboard</Button>
          ) : (
            <>
              <Button as={Link} to="/login" variant="ghost">Sign in</Button>
              <Button as={Link} to="/register">Get started</Button>
            </>
          )}
        </nav>
      </header>

      <section className="mx-auto max-w-6xl px-6 pt-10 pb-20 grid lg:grid-cols-2 gap-12 items-center">
        <motion.div initial="hidden" animate="show" transition={{ staggerChildren: 0.08 }}>
          <motion.span variants={fade} className="inline-block rounded-full bg-navy-50 px-3 py-1 text-xs font-semibold text-navy-700 ring-1 ring-navy-100">
            Verify Before You Believe. Think Before You Share.
          </motion.span>
          <motion.h1 variants={fade} className="mt-5 text-4xl sm:text-5xl font-extrabold leading-[1.1]">
            Don't Just Watch Videos. <span className="text-navy-500">Verify Their Truth.</span>
          </motion.h1>
          <motion.p variants={fade} className="mt-5 text-lg text-navy-600 max-w-xl">
            AI-powered video fact verification that helps you identify misinformation, analyse claims, and discover trusted evidence.
          </motion.p>
          <motion.div variants={fade} className="mt-8 flex flex-wrap gap-3">
            <Button as={Link} to={user ? '/dashboard' : '/register'} className="px-6 py-3">
              Analyse a Video <ArrowRight className="h-4 w-4" />
            </Button>
            <Button as="a" href="#features" variant="secondary" className="px-6 py-3">Explore Features</Button>
          </motion.div>
        </motion.div>

        <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }}
          className="card p-6 shadow-lift" aria-label="Example analysis preview">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-navy-400">Example result</div>
              <div className="font-display font-bold">"5 facts you learned in school"</div>
            </div>
            <span className="rounded-full bg-yellow-50 px-3 py-1 text-xs font-semibold text-yellow-800 ring-1 ring-yellow-200">Mixed Accuracy</span>
          </div>
          <div className="mt-5 flex h-4 w-full overflow-hidden rounded-full bg-navy-50">
            {DEMO_TIMELINE.map(([v, w], i) => (
              <motion.div key={i} initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: 0.4 + i * 0.07 }}
                style={{ width: `${w}%`, background: COLORS[v], transformOrigin: 'left' }} className="h-full border-r-2 border-white" />
            ))}
          </div>
          <div className="mt-5 space-y-3">
            {[
              ['false', '0:11', 'The Great Wall is visible from the Moon with the naked eye.'],
              ['verified', '0:18', 'Mount Everest is the highest mountain above sea level.'],
              ['misleading', '0:30', 'Napoleon was much shorter than average for his time.'],
            ].map(([v, t, text]) => (
              <div key={text} className="flex items-start gap-3 rounded-xl border border-navy-100 p-3">
                <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: COLORS[v] }} />
                <div className="text-sm"><span className="font-mono text-xs text-navy-400 mr-2">{t}</span>{text}</div>
              </div>
            ))}
          </div>
        </motion.div>
      </section>

      <section id="how" className="bg-white border-y border-navy-100">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <h2 className="text-3xl font-extrabold text-center">Four steps from video to verdict</h2>
          <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {STEPS.map(({ icon: Icon, title, text }, i) => (
              <motion.div key={title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
                transition={{ delay: i * 0.08 }} className="rounded-2xl bg-paper p-6 border border-navy-100">
                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-navy-900 p-2.5 text-white"><Icon className="h-5 w-5" /></div>
                  <span className="text-xs font-bold text-navy-400">STEP {i + 1}</span>
                </div>
                <h3 className="mt-4 font-bold text-lg">{title}</h3>
                <p className="mt-1 text-sm text-navy-600">{text}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-6xl px-6 pt-20">
        <h2 className="text-3xl font-extrabold text-center">Unique innovations</h2>
        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {INNOVATIONS.map(({ icon: Icon, title, text }) => (
            <div key={title} className="card p-5">
              <div className="w-fit rounded-xl bg-navy-900 p-2.5 text-white"><Icon className="h-5 w-5" /></div>
              <h3 className="mt-3 font-bold">{title}</h3>
              <p className="mt-1 text-sm text-navy-600">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20 grid sm:grid-cols-2 gap-6">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <div key={title} className="card p-6 flex gap-4">
            <Icon className="h-6 w-6 shrink-0 text-navy-600" />
            <div><h3 className="font-bold">{title}</h3><p className="mt-1 text-sm text-navy-600">{text}</p></div>
          </div>
        ))}
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16 text-center">
        <h2 className="text-2xl font-extrabold">Built with</h2>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {STACK.map((t) => <span key={t} className="rounded-full bg-white px-3 py-1.5 text-sm text-navy-700 ring-1 ring-navy-100">{t}</span>)}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-20">
        <div className="rounded-3xl bg-navy-900 px-8 py-12 text-center text-white">
          <h2 className="text-3xl font-extrabold">Verify Before You Believe. Think Before You Share.</h2>
          <Button as={Link} to={user ? '/dashboard' : '/register'} variant="secondary" className="mt-7 px-6 py-3">
            Start your first analysis <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </section>

      <footer className="border-t border-navy-100 py-8 text-center text-xs text-navy-400">
        LiveTruth Shield is a decision-support tool. AI verdicts can be wrong — always review the cited evidence.
      </footer>
    </div>
  )
}
