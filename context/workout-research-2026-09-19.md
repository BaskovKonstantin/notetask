# Workout research — 2026-09-19

Brainstorm only. No implementation.

## Current NoteTask Training

- Sidebar project **Тренировки** + right panel: today/30d counts, manual `workout_goals` (+1), recent sessions.
- `#view-workouts` composer (title, datetime, exercise/weight/reps rows) exists in HTML but `setView` always hides it; `loadWorkouts()` never called.
- DB: `workout_sessions(title, notes, started_at)` + `workout_sets(exercise, weight, reps, set_index)`. No program, week, routine, RPE/RIR, rest, exercise catalog.
- Live tasks: #161 Отжиматься 30 daily+hourly; #163 Планка 60с daily+hourly; #162 Силовые every_3_days. Stale: растяжка, Кегель, бассейн, HIIT. One log: «Ноги» squat 80×5. Goals empty.

## App landscape (2026)

Two product types:

1. **Logger** — you bring the plan, app records sets. [Hevy vs Strong vs Fitbod 2026](https://aifithub.io/articles/hevy-vs-strong-vs-fitbod-2026)
   - Strong: fastest log; free unlimited workouts, 3 routines; CSV export free; no programming. [JEFIT comparison Sep 2026](https://www.jefit.com/blog/fitbod-vs-strong-vs-jefit-vs-hevy)
   - Hevy: logger + social; free 4 routines / 3 months history / 7 custom exercises; Pro Trainer generator since Feb 2026. Same JEFIT comparison.
2. **Generator / program** — app decides next session or whole block
   - Fitbod: each session from recovery + equipment; **no weekly planner**. [JEFIT comparison](https://www.jefit.com/blog/fitbod-vs-strong-vs-jefit-vs-hevy)
   - JEFIT Elite: 12 weeks = 3×4-week blocks (On-Ramp, Accumulation, Intensification, Deload); sets/muscle + recovery. Same source (vendor blog).
   - Boostcamp: Program → weeks mapped → days → exercises with sets/reps/rest, supersets, RPE/AMRAP. [Boostcamp program creator](https://www.boostcamp.app/custom-program)
   - Liftosaur: Program → Week → Day → Exercise + progression script (`lp(2.5lb)`). [Liftosaur App Store](https://apps.apple.com/us/app/liftosaur-scriptable-workouts/id1661880849)

Must-have from loggers (progressive overload UX): previous set on the log screen, PRs, weekly volume. [PRPath 2025-12](https://prpath.app/blog/best-progressive-overload-trackers-2026.html)

Canonical model used by program apps:

```
Program (goal, split, duration)
  Week (optional meso)
    Day / Routine (Push / Pull / Legs / rest)
      Exercise (order + prescription: sets×reps, load, RPE/RIR, rest)
Session = instance of Day
  Logged sets (weight, reps, RPE, done)
```

NoteTask today is a broken logger with no Program layer. Tasks in Тренировки are reminders, not a plan.

## How to build a plan (evidence)

ACSM 2026 position stand (first major update since 2009, review ~30k participants): consistency > complex plan; train all major muscle groups **at least twice a week**; hypertrophy ~**10 sets per muscle/week**; strength heavier **≥80% 1RM**, 2–3 sets, key lifts first, ≥2 sessions/week; power 30–70% 1RM, fast concentric. Equipment type and training to failure not required. Complex periodization did not consistently beat simple progressive overload for general adults. [ACSM 2026](https://acsm.org/resistance-training-guidelines-update-2026)

Practical translation: effort **~2–3 RIR** ≈ failure for hypertrophy/strength with less fatigue. Hypertrophy load 30–100% 1RM if effort is there; push volume toward 15–20 sets/muscle if recovery allows. Periodization useful for peaking athletes, not the load-bearing variable for a personal tracker. [FitCraft ACSM explain](https://getfitcraft.com/science/acsm-2026-resistance-training-guidelines) citing Currier 2026 PMID 41843416 and Pelland 2026.

Older hypertrophy meta: >9 weekly sets/muscle larger effect; practical 12–20 sets/muscle when training 2×/week. [Schoenfeld 2017](https://pubmed.ncbi.nlm.nih.gov/27433992) [volume SR](https://pmc.ncbi.nlm.nih.gov/articles/PMC8884877)

Movement patterns to cover: push, pull, squat, hinge, carry/core. [GainFrame ACSM 2025 writeup](https://gainframe.app/blog/resistance-training-guidelines/) — treat as secondary to official 2026 stand.

## Implication for NoteTask

Do not ship Fitbod-style AI. Personal app: user already has a vague plan (daily push-ups/plank + «Силовые» every 3 days + one squat log). Closest analog: **Strong/Hevy logger + Boostcamp program layer** (week grid of days, start session from today's routine, show last numbers).

v1 likely:

- One active Program
- Week grid: named days + rest
- Routine = ordered exercises with target sets×reps
- Session log copies last weight/reps
- Tasks/reminders generated from the week, not the other way around
- Keep Здоровье separate; `workout_goals` probably replaced by volume/adherence from logs

JSON dumps: `/tmp/workout-apps.json`, `/tmp/workout-science.json`, `/tmp/workout-datamodel.json`
