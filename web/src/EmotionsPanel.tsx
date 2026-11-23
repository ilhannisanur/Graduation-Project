import { useEffect, useRef, useState } from 'react'
import Banner, { type Tone } from './Banner.tsx'
import { emotionAudioUrl, getEmotionSamples, type EmotionSample } from './studio.ts'

/**
 * "Why it is hard": one DJ voice in seven emotions, and the road from the first emotional
 * voice to a voice that checks its own emotion. Samples come from data/demo/emotions
 * (generated with the speech service; audio files are never committed).
 */

const TONES: Record<string, Tone> = {
  neutral: 'sun',
  happy: 'sun',
  excited: 'pink',
  surprised: 'pink',
  calm: 'mint',
  sad: 'sky',
  serious: 'lime',
}

type Step = { title: string; text: string; state: 'done' | 'now' | 'next' }

const PIPELINE: Step[] = [
  {
    title: 'Context',
    text: 'Time of day, weather, news and special days set the mood of the moment.',
    state: 'next',
  },
  {
    title: 'Music by mood',
    text: 'Every song has a valence and an energy; the DJ picks what fits the moment.',
    state: 'done',
  },
  {
    title: 'Emotion of the words',
    text: 'A model reads the text and proposes 2–3 tones; the LLM writes the DJ line.',
    state: 'next',
  },
  {
    title: 'Emotional voice',
    text: 'Open-source TTS (Orpheus) speaks the line in the chosen emotion.',
    state: 'done',
  },
  {
    title: 'Prosody control',
    text: 'Our own WORLD-vocoder code adjusts speed, pitch and pauses per emotion.',
    state: 'next',
  },
  {
    title: 'Emotion check',
    text: 'Our speech-emotion model listens to the result. Wrong emotion? Up to 3 new takes, the best one goes on air.',
    state: 'next',
  },
  {
    title: 'One shared broadcast',
    text: 'Songs, DJ and listener requests in one live stream for everyone.',
    state: 'now',
  },
]

const STATE_LABEL = { done: 'Working', now: 'This sprint', next: 'Next' } as const

export default function EmotionsPanel() {
  const [samples, setSamples] = useState<EmotionSample[]>([])
  const [playing, setPlaying] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    getEmotionSamples()
      .then(setSamples)
      .catch(() => {})
    return () => audioRef.current?.pause()
  }, [])

  function play(sample: EmotionSample) {
    const audio = (audioRef.current ??= new Audio())
    if (playing === sample.file) {
      audio.pause()
      setPlaying(null)
      return
    }
    audio.src = emotionAudioUrl(sample.file)
    audio.onended = () => setPlaying(null)
    audio.play().then(
      () => setPlaying(sample.file),
      () => setPlaying(null),
    )
  }

  return (
    <>
      <Banner tone="lime" title="One voice, seven feelings">
        The hard part of this project: making a synthetic voice sound the way the moment feels, and
        checking that it really does.
      </Banner>

      <section className="emotion-grid" aria-label="Emotion samples">
        {samples.length === 0 && (
          <p className="panel muted">
            No samples yet. Run <code>python ../scripts/demo_samples.py</code> from the backend
            folder with the speech service on.
          </p>
        )}
        {samples.map((s) => (
          <button
            key={s.file}
            type="button"
            className={`emotion-card tone-${TONES[s.emotion] ?? 'sun'}`}
            aria-pressed={playing === s.file}
            onClick={() => play(s)}
          >
            <span className="emotion-name">{s.label}</span>
            <span className="emotion-text">“{s.text}”</span>
            <span className="emotion-play" aria-hidden="true">
              {playing === s.file ? 'Playing…' : 'Play'}
            </span>
          </button>
        ))}
      </section>

      <section className="panel tone-sky" aria-labelledby="pipeline-title">
        <h2 id="pipeline-title" className="panel-title">
          From a moment to a voice
        </h2>
        <ol className="pipeline">
          {PIPELINE.map((step, i) => (
            <li key={step.title} className={`pipe-step pipe-${step.state}`}>
              <span className="pipe-num">{i + 1}</span>
              <span className="pipe-body">
                <strong>{step.title}</strong>
                <span>{step.text}</span>
              </span>
              <span className="pipe-state">{STATE_LABEL[step.state]}</span>
            </li>
          ))}
        </ol>
      </section>
    </>
  )
}
