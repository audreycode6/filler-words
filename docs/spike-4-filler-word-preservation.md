# Spike 4: Filler Word Preservation

Script: [`spikes/spike4_filler_word_preservation.py`](../spikes/spike4_filler_word_preservation.py)


**Question:** Does `SFSpeechRecognizer` preserve filler words ("um", "uh",
"like") anywhere in its output, even if stripped from `formattedString()`?

**Method:**

1. Copy [Spike 2](spike-2-stt-streaming.md)'s script as the base (permission checks, request +
   recognizer + tap setup, run-loop pump).
2. In `recognition_result_callback`, iterate
   `result.bestTranscription().segments()` and print each segment's
   `.substring()` and `.confidence()`, alongside the existing
   `formattedString()` print.
3. Also print each segment's `.alternativeSubstrings()` if non-empty.
4. Speak a test sentence with several clearly-enunciated "um"/"uh"/"like"
   fillers placed cleanly between real words.
5. Run a control sentence with no filler words, to sanity-check the
   segment-printing code itself.
6. Compare: do filler words ever appear in `segments()` or
   `alternativeSubstrings()`, even when absent from `formattedString()`?

**Result:**

Across two runs (9 usable filler-word instances: 4 "um", 5 "uh"), 0 fillers were recoverable at any level
tested: not in `formattedString()`, not as a segment `.substring()`, and
not in any segment's `.alternativeSubstrings()`. Empty on every segment,
every run — including on real words, suggesting this recognizer
configuration doesn't populate alternatives at all.

- Run 1 (not shown in the table below, but counted in the tally): the spoken
  sentence "My name UM is not UM bob sherbert" produced the transcript "My
  name is not Bob sherbet" — both "um" instances dropped with zero trace.
- Run 2 spoken sentence: "My name UM is not UH bob sherbert. UH I like love
  that UH short UH hairdo. And I think UH I'm going to UM talk about." Final
  settled transcript: "My name is not a Bob sherbet I like love that a short
  hairdo and I think I'm going to him talk about."

Run 2 word-by-word alignment (spoken vs. transcribed):

- "My name" → My name (normal)
- **UM** → _(nothing)_ — dropped
- "is not" → is not (normal)
- **UH** → **'a'** — substituted
- "bob sherbert" → Bob sherbet (normal)
- **UH** → _(nothing)_ — dropped
- "i like love that" → I like love that (normal)
- **UH** → **'a'** — substituted
- "short" → short (normal)
- **UH** → _(nothing)_ — dropped
- "hairdo" → hairdo (normal)
- "and i think" → and I think (normal)
- **UH** → _(nothing)_ — dropped
- "im going to" → I'm going to (normal)
- **UM** → **'him'** — substituted
- "talk about" → talk about (normal)

Combined tally: 6 of 9 fillers silently dropped with no trace; 3 of 9
replaced with a real, phonetically-similar, contextually-plausible word
("uh" → "a" ×2, "um" → "him" ×1); 0 of 9 recoverable via any tested API
surface.

Transcription excerpt (two consecutive firings, real logged output,
showing "a" appear at full confidence exactly where "uh" was spoken, then
collapse on the very next revision while the surrounding real words barely
move):

```
[+4.39s] My name is not a
  segment: 'My' (confidence=1.00)
  segment: 'name' (confidence=1.00)
  segment: 'is' (confidence=1.00)
  segment: 'not' (confidence=1.00)
  segment: 'a' (confidence=1.00)
[+4.49s] My name is not a
  segment: 'My' (confidence=0.93)
  segment: 'name' (confidence=0.92)
  segment: 'is' (confidence=0.92)
  segment: 'not' (confidence=0.92)
  segment: 'a' (confidence=0.20)
```

Confidence on the substituted words is notably unstable across revision
passes, e.g. `'him'` swings 1.00 → 1.00 → 0.78 → 1.00 → 0.12 → 1.00, `'a'`
(before "Bob") swings 1.00 → 0.20 → 1.00 → 0.39 → 1.00 → 0.23 — versus
genuine words like "My"/"name", which stay stable in the 0.85-1.00 range
throughout. Neighboring real words ("short", "hairdo") also dip during the
same revision passes (0.04-0.67), so this isn't a clean, isolated signal.

**Interpretation:**

- **Confirms and sharpens [Spike 3](spike-3-thread-safety.md)'s side-finding**: it's not just
  `formattedString()` doing final cleanup; `segments()` and
  `alternativeSubstrings()` never contain "um"/"uh" either, at any point in
  either run. This is a hard blocker at the recognizer/model level, not a
  formatting choice you can route around by reading a lower-level API.
- **Silent dropping isn't the only failure mode**
  Roughly a third of fillers get replaced with a real, plausible-sounding
  word ("uh" → "a", "um" → "him") rather than just vanishing. There's no
  way to distinguish a substituted-filler "a" from a genuine spoken "a"
  using the text alone.
- **Confidence-score volatility is a tentative lead, not a proven signal.**
  Substituted words show much larger swings across revisions than genuine
  words, but nearby real words dip too, so it's noisy rather than a clean
  isolated tell.
- **This changes the project's scope, not just the implementation.**
  `SFSpeechRecognizer` cannot detect "um"/"uh" via any text-based API
  surface, at any level tested. Rather than solve this with a heavier
  architecture change (a cloud STT with disfluency-removal disabled, or a
  specialized local model), the v1 goal was updated at this point: detect
  filler words/phrases that survive as real text (e.g. "like", "so",
  "actually", "basically"), rather than all disfluencies. "um"/"uh" are out
  of scope for v1.
- **Real-word survival is already evidenced, not assumed.** "like" appears
  correctly transcribed three separate times across two spikes (Spike 2's
  "I like to eat..." and this spike's two runs) — never dropped, never
  substituted, unlike every "um"/"uh" instance. Every other ordinary word
  spoken across all four spikes transcribed reliably too. The failure mode
  observed is specific to filled-pause disfluencies, not real vocabulary.

**Deferred Decisions:**

- Whether the tracked-word list is a fixed curated default, fully
  user-configurable, or both (default list + user customization) is a
  product decision, not built here.
  - Leaning toward shipping a fixed
    default list first (lowest engineering risk, proves the matching
    pipeline end-to-end), then adding user-configurable words as a fast
    follow, since only the word _source_ changes, not the matching mechanism.
- Acoustic, non-ASR detection of "um"/"uh" (pure DSP signal processing —
  pitch-stability + energy + duration heuristics on the raw audio buffer,
  running alongside `SFSpeechRecognizer` rather than replacing it) is a
  possible v2 expansion, not required for v1. Matches how purpose-built
  filler detectors work in the wild (per Interspeech 2022 benchmark
  research); the raw audio buffer is already available in every spike's
  `tap_callback`, so this wouldn't require reworking Spikes 1-3.
- Word-boundary-aware matching for the matcher itself (e.g. "so" shouldn't
  match inside "also") and how it should handle partial-result revision
  (per Spike 2's finding that words can be silently corrected or retracted
  before finalizing) are implementation decisions for the matcher itself,
  deliberately not designed here.

**Status:** Spike complete. Core question answered with a split result: of the three
words named in the original question ("um", "uh", "like"), "like" survives
reliably as real text across every instance observed, while "um" and "uh"
are unrecoverable at any tested API level (`formattedString()`,
`segments()`, `alternativeSubstrings()`) — confirmed a hard blocker, not a
formatting quirk. This directly shaped the project-level scope decision taken
at the time: v1 would track real-word fillers only ("like", "so", "actually",
"basically", etc.), rather than pure disfluency sounds with no stable word to
match against ("um", "oh", "uh", "er"). Acoustic DSP-based detection of those
sound-based fillers was flagged as a possible future v2 expansion, rather than
a v1 requirement.

