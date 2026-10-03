# 01 · Mission, pitch, and how we meet the Air track

## Mission (what we tell a Delhi person)
Your trip has two costs nobody shows you: what you breathe, and what you put into the air. ALive shows both before you go, counts both while you travel, and gives you the way that's lighter on your lungs and on Delhi.

## The 4-line pitch (plain words, every line backed by something live)
> Every trip in Delhi costs you smoke, and costs Delhi smoke.
> ALive shows both before you leave: what you'll breathe, and what your ride will put out.
> While you travel it counts both, live, and picks the way that's lighter on both.
> Every trip, anonymously, adds to a live map of what Delhi breathes and emits on its roads.

The line for one judge to repeat to another: **"Google Maps prices a trip in minutes. ALive prices it in breath and in smoke."**

Why this pitch survives: each line maps to something a judge can see working (doc 09 acceptance list). There's no "might", no "in future", and no city-wide claim we can't measure.

## Hackathon requirement mapping (Air track: reduce exposure and emissions, real data, on AWS)
| What judges score | What we show | Where it lives |
|---|---|---|
| **Exposure reduction** | Per-trip dose band for every option; live breath counter; arrival receipt vs the option you didn't take | app + `/compare`, `/observe` |
| **Emissions reduction** | Per-trip emission band from the vehicle you declared; "lighter on Delhi" pick; trips switched to lower-emission choices, counted | app + `/compare` + dashboard |
| **Real data** | CAMS model + CPCB/OpenAQ stations + NASA FIRMS fires + DMRC GTFS + Delhi Traffic Police black spots; data age shown everywhere | `/health`, `/city` |
| **Technical depth** | Kriged field with honest uncertainty; COPERT-structure emissions with cold start and idle; C++ engine with published benchmarks; validation report vs 3,550 station-hours | docs/plan/06, 08; `field_validation.md` |
| **AWS, visible** | ECS Fargate + NLB, ECR, CodeBuild, S3 archive, DynamoDB aggregates, EventBridge schedules, CloudWatch, Secrets Manager, **Amazon Location (maps + places + routes)** | console shots in the video |
| **Usability** | A person who has never heard "AQI" plans a trip in 3 taps; no jargon on any consumer screen | doc 02 |
| **Working execution** | Android APK on a real phone against the live AWS URL; iOS on simulator | doc 09 |

## The 3:00 video arc
| t | Beat | On screen |
|---|---|---|
| 0:00–0:15 | Problem | Phone on a Delhi road; line 1 of the pitch |
| 0:15–0:45 | Search + compare | Type "select citywalk", result in <100 ms; options list: each with time, breath, smoke-out |
| 0:45–1:20 | Live trip | Navigation on the dark map; two counters ticking; voice turn; reroute |
| 1:20–1:40 | Receipt | Arrival card: breathed vs alternative; emitted vs your usual |
| 1:40–2:10 | Delhi today | Consumer "Delhi today" sheet: the live map of the city, trips counted, honest labels |
| 2:10–2:40 | Under the hood | AWS console (ECS, Location, DynamoDB, EventBridge, CloudWatch); C++ benchmark table; validation report |
| 2:40–3:00 | Close | Pitch line 4 + repo URL |

Recording rules: real phone, real network, real AWS URL. One take per beat; fallback footage is the same flow recorded on the simulator against the same server.
