/**
 * The radio's mixing desk, built on Web Audio:
 *
 *   voice   <audio> → level → high-pass 90 Hz → presence +2.5 dB @ 3 kHz → compressor 3:1 ─┐
 *   music A <audio> → level ────────────────────────────────────────────────────────────────┤
 *   music B <audio> → level ────────────────────────────────────────────────────────────────┤
 *                                       master: compressor/limiter → listener volume → out ◄┘
 *
 * Two music channels let one song fade out while the next fades in; the voice channel lets
 * the DJ talk over a song intro. Without Web Audio the elements play directly and levels
 * change at once instead of fading.
 */

/** The song's level while the DJ talks over its intro: about −18 dB. */
export const DUCK_LEVEL = 0.12

export type Channel = {
  readonly el: HTMLAudioElement
  /** Moves the channel's level to `to` (0..1) over `seconds` (at once when 0), from `from`
   *  if given, else from the current level. */
  fade: (to: number, seconds?: number, from?: number) => void
  /** Stops the sound and forgets the file. */
  silence: () => void
}

/** Steps used to draw an equal-power curve with cancellable linear ramps. */
const FADE_STEPS = 12

export class Mixer {
  readonly voice: Channel
  readonly music: readonly [Channel, Channel]
  private ctx: AudioContext | null = null
  private output: GainNode | null = null
  private readonly gains = new Map<HTMLAudioElement, GainNode>()
  private readonly levels = new Map<HTMLAudioElement, number>()
  private volume: number

  constructor(volume: number) {
    this.volume = volume
    this.voice = this.makeChannel()
    this.music = [this.makeChannel(), this.makeChannel()]
  }

  get channels(): Channel[] {
    return [this.voice, ...this.music]
  }

  /** Builds the graph once and wakes it. Call inside the listener's tap (autoplay rules). */
  unlock(): void {
    if (!this.ctx) this.build()
    if (this.ctx?.state === 'suspended') void this.ctx.resume().catch(() => {})
  }

  setVolume(volume: number): void {
    this.volume = volume
    if (this.output && this.ctx) {
      this.output.gain.setTargetAtTime(volume, this.ctx.currentTime, 0.03)
    } else {
      for (const channel of this.channels) this.applyFallback(channel.el)
    }
  }

  close(): void {
    for (const channel of this.channels) channel.silence()
    void this.ctx?.close().catch(() => {})
    this.ctx = null
  }

  private makeChannel(): Channel {
    const el = new Audio()
    el.preload = 'auto'
    this.levels.set(el, 1)
    this.applyFallback(el)
    return {
      el,
      fade: (to, seconds = 0, from) => this.fade(el, to, seconds, from),
      silence: () => {
        el.pause()
        el.removeAttribute('src')
        el.load()
      },
    }
  }

  private build(): void {
    const Context =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Context) return
    const ctx = new Context()

    // Master: a gentle compressor that also catches peaks, so songs mastered at different
    // loudness sit closer together, then the listener's volume.
    const master = ctx.createDynamicsCompressor()
    master.threshold.value = -14
    master.knee.value = 8
    master.ratio.value = 4
    master.attack.value = 0.005
    master.release.value = 0.25
    const output = ctx.createGain()
    output.gain.value = this.volume
    master.connect(output).connect(ctx.destination)

    // "Radio voice": cut rumble, a little presence, an even level, then make-up gain.
    const highPass = ctx.createBiquadFilter()
    highPass.type = 'highpass'
    highPass.frequency.value = 90
    highPass.Q.value = 0.7
    const presence = ctx.createBiquadFilter()
    presence.type = 'peaking'
    presence.frequency.value = 3000
    presence.Q.value = 1
    presence.gain.value = 2.5
    const voiceComp = ctx.createDynamicsCompressor()
    voiceComp.threshold.value = -22
    voiceComp.knee.value = 6
    voiceComp.ratio.value = 3
    voiceComp.attack.value = 0.005
    voiceComp.release.value = 0.2
    const makeUp = ctx.createGain()
    makeUp.gain.value = 1.4 // about +3 dB back after the compressor
    highPass.connect(presence).connect(voiceComp).connect(makeUp).connect(master)

    for (const channel of this.channels) {
      const el = channel.el
      el.volume = 1 // levels now live in the graph
      const gain = ctx.createGain()
      gain.gain.value = this.levels.get(el) ?? 1
      ctx.createMediaElementSource(el).connect(gain)
      gain.connect(channel === this.voice ? highPass : master)
      this.gains.set(el, gain)
    }
    this.ctx = ctx
    this.output = output
  }

  private fade(el: HTMLAudioElement, to: number, seconds: number, start?: number): void {
    this.levels.set(el, to)
    const gain = this.gains.get(el)
    if (!gain || !this.ctx) {
      this.applyFallback(el)
      return
    }
    const param = gain.gain
    const now = this.ctx.currentTime
    // `param.value` only changes once audio is rendered, so a level set a moment ago is not
    // there yet: callers that know where the fade starts say so.
    const from = start ?? param.value
    param.cancelScheduledValues(now)
    param.setValueAtTime(from, now)
    if (seconds <= 0 || from === to) {
      param.setValueAtTime(to, now)
      return
    }
    // An equal-power curve (sine in, cosine out) so a crossfade does not dip in the middle.
    // Drawn with linear ramps because those can be cancelled half-way (skip, pause).
    for (let i = 1; i <= FADE_STEPS; i++) {
      const t = i / FADE_STEPS
      const shape = to > from ? Math.sin((t * Math.PI) / 2) : 1 - Math.cos((t * Math.PI) / 2)
      param.linearRampToValueAtTime(from + (to - from) * shape, now + seconds * t)
    }
  }

  private applyFallback(el: HTMLAudioElement): void {
    if (this.gains.size > 0) return
    el.volume = Math.min(1, Math.max(0, (this.levels.get(el) ?? 1) * this.volume))
  }
}
