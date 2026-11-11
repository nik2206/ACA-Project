# ACA-Project

Advanced Computer Architecture course project: **Exploring Performance–Energy Trade-offs Using
Energy Roofline Models**, reproducing Choi et al., "A roofline model of energy" (IPDPS 2013) and
"Algorithmic time, energy, and power on candidate HPC compute building blocks" (IPDPS 2014) on a
hybrid Intel laptop CPU (Core i5-13420H), with turbo on and turbo off.

Authors: Sai Abhinav (measurements) and Nikhil (modelling, analysis and report).

| Path | Contents |
|---|---|
| `References/` | the two papers |
| `Implementation Plan.md` | the project plan: model formulas, deliverables, workstreams |
| `energy-roofline/` | benchmarks, data, analysis code; see its [README](energy-roofline/README.md) |
| `energy-roofline/report/report.md` (`.pdf`, `.html`) | the report |
| `energy-roofline/report/slides/index.html` | the slide deck |
| `energy-roofline/report/viva_guide.md` | viva study guide: derivations, 62 Q&As, pros and cons, open questions, cheat sheet |
| `OPUS_TASK.md` | the plan used to produce the viva guide |

Main result: the model fits the CPU closely (median energy error 1.7%) and race-to-halt holds at a
fixed clock (B_τ > B̂_ε with turbo on and off), but turning turbo off makes every kernel 2–3× more
energy-efficient, which the model cannot predict because its constants belong to one frequency
and voltage.
