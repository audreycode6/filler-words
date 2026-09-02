# Spike 4: Filler Word Preservation

Script: [`spikes/spike4_filler_word_preservation.py`](../spikes/spike4_filler_word_preservation.py)


**Question:** Does `SFSpeechRecognizer` preserve filler words ("um", "uh",
"like") anywhere in its output, even if stripped from `formattedString()`?

**Method:** [Spike 2](spike-2-stt-streaming.md)'s script, extended to print each
segment's `.substring()`, `.confidence()` and `.alternativeSubstrings()`
alongside the existing `formattedString()`. Two runs of a sentence with
clearly-enunciated "um"/"uh"/"like" fillers placed between real words, plus a
control sentence with no fillers to check the printing itself.

**Result:**

Across 2 runs (9 usable filler-word instances: 4 "um", 5 "uh"), 0 fillers were recoverable at any level
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

Transcription excerpt (2 consecutive firings, real logged output,
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

- **"um" and "uh" cannot be recovered at any level, and the transcript does not
  simply omit them.** They are absent from `formattedString()`, `segments()` and
  `alternativeSubstrings()` alike, so this is a blocker at the model level rather
  than a formatting choice a lower-level API routes around. About a third are
  replaced by a real, plausible word ("uh" → "a", "um" → "him"), which the text
  alone cannot distinguish from the same word genuinely spoken.
- **Confidence scores cannot separate the two.** Substituted words swing more
  across revisions than genuine ones, but nearby real words dip too.
- **Real words survive reliably.** "like" transcribed correctly 3 times across
  this spike and Spike 2, never dropped and never substituted, as did every other
  ordinary word spoken. The failure is specific to filled pauses.
- **So the scope narrowed to words that survive as real text.** Detecting "um"
  and "uh" would take a heavier architecture: a cloud recognizer with disfluency
  removal disabled, or a specialized local model.

**Status:** Spike complete, with a split result: of the 3 words named in the
question, "like" survives reliably while "um" and "uh" do not, at any level.
Carried forward: acoustic detection of sound-based disfluencies as a possible
later expansion.

