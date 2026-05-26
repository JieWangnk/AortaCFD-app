# AortaCFD documentation

User-facing guides for installing, learning, and running AortaCFD.

## Where to start

| You want to… | Go to |
|---|---|
| Install + run your first case | the top-level [README.md](../README.md) |
| Configure a run (every config key explained) | [`user-guide/configuration.md`](user-guide/configuration.md) |
| Tune the mesh (`cells_per_diameter`, target sizes, span) | [`user-guide/mesh-specification.md`](user-guide/mesh-specification.md) |
| Understand mesh-quality warnings before trusting results | [`user-guide/mesh-quality-warnings.md`](user-guide/mesh-quality-warnings.md) |
| Add boundary layers (auto y+ or manual) | [`user-guide/boundary-layers.md`](user-guide/boundary-layers.md) |
| Regenerate numerics from existing mesh quality | [`user-guide/regenerate-numerics.md`](user-guide/regenerate-numerics.md) |
| Learn the pipeline end-to-end on one canonical patient | [`tutorial/`](tutorial/README.md) — 8-week course, 9 sessions |
| Run parametric studies / cohorts (Block A → D workflow) | [`workshop/`](workshop/README.md) — 6 lessons + cheat sheet |

## What's where

```
docs/
├── README.md                                  (this index)
├── user-guide/
│   ├── configuration.md                       (every config key, with examples)
│   ├── mesh-specification.md                  (cells_per_diameter / target / span)
│   ├── mesh-quality-warnings.md               (must-read caveats)
│   ├── boundary-layers.md                     (auto-y+ + manual modes)
│   └── regenerate-numerics.md                 (adapt fvSchemes/fvSolution to mesh)
├── tutorial/                                  (8-session PhD course on one patient case)
└── workshop/                                  (parametric-study / cohort workflow)
```

For first-time setup, the top-level [README](../README.md) is the
single source of truth.
