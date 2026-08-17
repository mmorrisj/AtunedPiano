# Advances in Computational Piano Tuning Since Hinrichsen (2012): A Technical Review for a Python Reimplementation of the Entropy Piano Tuner

## TL;DR
- The entropy-minimization idea (Hinrichsen 2012) has been extended, made reproducible, and partly superseded: the single most implementable upgrade is to **replace Hinrichsen's random ±1-cent Monte Carlo with a global optimizer (PSO or CMA-ES) run over a decomposed inharmonicity + tuning model** rather than raw summed spectra — this fixes the non-reproducibility that killed the original.
- For a hobbyist Python build, the strongest architecture is **hybrid**: estimate B per note with a robust classical method (MAT / partial-frequency-deviation / NMF), generate a smooth base curve with the Rigaud–David–Daudet parametric model, then optionally add entropy- or dissonance-based local refinement — this is what the field has converged on, and it is all doable with numpy/scipy without inheriting the GPL EPT code.
- Neural pitch models (CREPE/SPICE/Basic Pitch) and "AI tuning" marketing (pianoscope Pro, CyberTuner) are **not** worth adopting: for isolated piano notes, classical FFT peak-picking + least-squares on the B-model is more accurate, faster, and interpretable; no vendor publishes a verifiable technical basis for "AI curves."

## Key Findings

1. **The citation graph is small but coherent.** Hinrichsen 2012 has been cited only a modest number of times — Scite.ai's citation report logs 17 citation statements (14 "Mentioning," 0 "Supporting," 0 "Contrasting," 3 "Unclassified") and Semantic Scholar lists 14 citations, i.e. roughly a dozen-and-a-half, not "dozens." The substantive descendants are Szwajcowski & Pilch (2020, PSO reimplementation), Bakogiannis et al. (ENTROTUNER, 2020), the Aalto group (Tuovinen/Hu/Välimäki 2019; Shah & Välimäki 2020), Giordano (2015, dissonance-based Railsback explanation), Rigaud–David–Daudet (2013, parametric inharmonicity/tuning), and the Jaatinen perceptual series (2019–2023). Most "mention" rather than "contrast"; genuine disagreement is about whether entropy is the right objective at all versus sensory-dissonance or beat-rate models.

2. **PSO makes entropy tuning reproducible** — the key contribution of Szwajcowski & Pilch. The original method's fatal flaw (many local minima, non-reproducible runs) is real and acknowledged by Hinrichsen himself.

3. **ENTROTUNER formalizes the objective and benchmarks optimizers**, and importantly shows the 1-cent quantization step materially affects results.

4. **Inharmonicity estimation is a solved-enough problem** with several cheap, robust classical methods; the hard regions remain extreme bass and high treble.

5. **The field is split on the objective function**: spectral entropy vs. Sethares/Plomp-Levelt sensory dissonance vs. explicit beat-rate models. Giordano showed dissonance minimization reproduces the Railsback curve.

6. **Perceptual work supports octave stretching as genuine**, and one careful study found neighboring strings do NOT meaningfully contaminate single-string B measurement — a useful, reassuring result for recording protocol.

## Details

### 1. The citation graph since 2012 — who extends, refines, or contrasts

Hinrichsen's paper (arXiv:1203.5101; Rev. Bras. Ens. Fís. 34(2):2301, 2012) proposed tuning by minimizing the Shannon entropy H = −Σ p_m ln p_m of a logarithmically-binned (1 cent/bin), A-weighted, summed power spectrum of all 88 recorded notes, optimized by a zero-temperature Monte Carlo (random ±1 cent pitch change, accept if entropy drops). The paper is candid about limitations: many local minima, non-reproducible results, sensitivity to A-weighting vs. loudness (loudness gives absurd bass stretch), and that Gaussian jnd-smoothing "does not improve the results."

Substantive citing works:
- **Szwajcowski & Pilch 2020** (Applied Acoustics 166:107359) — reimplement with PSO for reproducibility. *Supporting/extending.*
- **Bakogiannis et al. 2020 (ENTROTUNER)** (IEEE Access 8:53185–53195) — generalize the objective, add tuning-rule/scale constraints, benchmark optimizers, study the quantization step. *Extending.*
- **Rigaud, David & Daudet 2013** (JASA 133(5):3107–3118) — parametric inharmonicity + tuning model; an alternative to entropy that is arguably more practical. *Contrasting approach, complementary.*
- **Giordano 2015** (JASA 138(4):2359–2366) — explains the Railsback stretch via inharmonicity + Plomp-Levelt/Sethares sensory dissonance. Its abstract states the minimum-sensory-dissonance prediction "agree[s] with the well known 'Railsback stretch,' the average tuning curve produced by skilled piano technicians." A rival objective function. *Contrasting.*
- **Tuovinen, Hu & Välimäki 2019** (SMC) and **Shah & Välimäki 2020** (Applied Sciences 10(6):1983) — beat-rate/interval-based automatic tuning; the latter derives a simple, listening-test-validated rule for high treble. *Contrasting/complementary.*
- **Jaatinen et al. 2019, 2021, 2022, 2023** — psychoacoustics of octave enlargement and inharmonicity-driven tuning; validate that stretch is perceptual as well as physical. *Supporting context.*
- **Hinrichsen 2016** ("Revising the Musical Equal Temperament," Rev. Bras. Ens. Fís. 38) — uses entropy to argue for a slightly stretched *temperament* (ratio > 2^(1/12)); note this is about temperament, not inharmonicity stretch, and is a distinct topic.
- **Menrath 2021** (KUG Graz Toningenieur-Projekt, "Towards libre piano tuning software based on psychoacoustic features") — an open, detailed critique of EPT and a roughness/fluctuation-strength alternative; the single most useful secondary source for a reimplementer.

### 2. Optimization methods

**Szwajcowski & Pilch (2020), "Optimization of piano tuning by means of spectral entropy minimization," Applied Acoustics 166:107359, DOI 10.1016/j.apacoust.2020.107359.**

Core idea: keep Hinrichsen's spectral-entropy objective but replace the Monte Carlo with **Particle Swarm Optimization** (the Yarpiz "ypea102" MATLAB implementation, Heris 2015) to obtain reproducible results. The paper explicitly frames its contribution as repeatability: "By providing repeatability of results, our algorithm allows spectral entropy minimization to be reliably compared with alternative methods."

Confirmed specifics:
- Optimizer: Yarpiz PSO.
- Test material: a **free Kawai K18 upright-piano sample library** (SFZ-mapped WAV), chosen because uprights have stronger inharmonicity than grands. The library samples "every third piano key (all of the A, C, D# and F# sounds)" at seven dynamic levels.
- Entropy minimized "in octaves" — a departure from Hinrichsen's simultaneous all-88-key summation.
- Listening test conducted per **ITU-R BS.1116-3** ("small impairments"), comparing four tunings rendered as SFZ virtual instruments: base-frequency (12-ET), autocorrelation-based, spectral-entropy (PSO), and aural. Their Railsback curves for aural, autocorrelation, and entropy tunings "feature similar trends."
- Result headline: minimizing spectral entropy leads, across most of the range, to octave stretching consistent with well-documented Railsback behavior.

**Honest gap:** The full text is paywalled (ScienceDirect); the exact PSO hyperparameters (swarm size, iterations, inertia weight w, cognitive/social coefficients c1/c2, variable bounds), quantified convergence/repeatability (SD in cents), runtime vs. Monte Carlo, listener count, and numeric subjective ratings could not be verified from open sources and should be obtained from the authors (AGH Kraków) or via institutional access. A "20 arguments / 0–20 kHz kernel centers" snippet circulating on ResearchGate belongs to a *different* Szwajcowski paper (HRTF/RBF) and must not be attributed to the piano work.

**Other global optimizers:** ENTROTUNER (below) directly benchmarks PSO, Simulated Annealing, and Hinrichsen's quantized method on the same objective. No published work applies **CMA-ES, Bayesian optimization, or differentiable/gradient-based** formulations to the *entropy* tuning objective specifically — this is a genuine open niche. (DDSP-piano uses gradient-based fitting of an inharmonicity model, but for synthesis, not tuning-curve optimization; see §5.)

*Assessment:* PSO is worth adopting for reproducibility, but for a Python build the better move is to note **why** the raw entropy landscape is so multimodal (summed ~10,800-bin spectra, cent-quantized shifts) and instead optimize over a **low-dimensional parametric model** (Rigaud) where even L-BFGS or CMA-ES converges cleanly. PSO on the raw objective is easy (`pyswarms`) but computationally heavy and still landscape-limited.

### 3. ENTROTUNER (Bakogiannis, Polychronopoulos, Marini, Terzēs, Kouroupetroglou 2020)

**IEEE Access 8:53185–53195, DOI 10.1109/ACCESS.2020.2981007.** Open-access.

Architecture and differences from Hinrichsen:
- Recasts tuning as constrained mathematical optimization that explicitly incorporates (a) the instrument as a sound-production mechanism, (b) the relevant musical scale(s), and (c) the player's interaction — modeled as a system that follows **tuning rules** to maximize partial overlap (harmonicity), coded as entropy minimization of the aggregated spectrum. Where Hinrichsen sums raw recorded spectra, ENTROTUNER adds explicit scale/tuning-rule constraints and applies it to a wind instrument (the ancient Greek aulos) as the case study.
- Uses the same entropy-of-overlap intuition (Fig. 1 in the paper: non-overlapping peaks H≈9.69 bit; maximal overlap minimizes H).

Optimizer benchmark (their Table 2): they compare **PSO, Simulated Annealing, and Hinrichsen's original quantized method**. Findings: Simulated Annealing was least efficient (did not approach the overall best cost 13.4974); Hinrichsen's method with quantization reached its best cost (13.3958) in under 700 iterations but was not proven efficient relative to the overall best. Critically, they run Hinrichsen's technique **two ways — with and without the 1-cent quantization step** — demonstrating the quantization choice changes the achievable optimum.

Reported quantitative improvements vs. traditional (physical-model-based) methods: **entropy decreased by 0.341 bits, eleven additional consonant intervals, and 47.8% higher "tuning quality"** for the Aulos of Louvre case; a second case (Aulos of Poseidonia) gave 0.197 bits, 5 additional consonant intervals, 46.2% more tuning quality.

*Assessment:* The scale-constraint idea is directly portable and valuable — it addresses Hinrichsen's own observation that restricting to subsets of intervals destabilizes his method (drives toward just intonation), by instead adding equal-temperament as an explicit constraint/penalty rather than relying on all-key summation. The specific numbers are for a wind instrument, not a piano, so don't over-generalize. The with/without-quantization finding is a direct warning for your implementation (see §9).

### 4. Inharmonicity (B) estimation

Physical model: f_n = n·f_1·√(1 + B·n²). Typical B: ~0.0002 (bass) to ~0.4 (extreme treble) per Hinrichsen; Tuovinen's Yamaha grand data shows B ≈ 1e−4 in the long bass rising toward ~1e−2 in the treble.

Key methods, roughly in increasing sophistication:
- **Fletcher-style two-partial solve / MAT (Median-Adjustive Trajectories, Hodgkinson et al. 2009).** Solve B from two known partials, then iteratively find higher partials using running medians of B and f0 to reject outliers. Fast, robust, and the Aalto group's choice for real-time use. Very implementable in Python.
- **Partial Frequencies Deviation (PFD) — Rauhala, Lehtonen & Välimäki 2007** (JASA 121(5):EL184–EL189). Minimize deviation between expected partial frequencies and measured spectral peaks via an adaptive-step iterative scheme. Reported to match inharmonic-comb-filter accuracy at a "fraction of the time." Also the Rauhala & Välimäki 2007 ICMC F0-via-PFD variant.
- **Inharmonic comb filters (Galembo & Askenfelt 1999)** — accurate but computationally heavy; largely superseded by PFD/MAT for speed.
- **Rigaud, David & Daudet 2013 (JASA 133(5):3107–3118)** — NMF with an inharmonicity constraint (building on their EUSIPCO 2012 work "Does inharmonicity improve an NMF-based piano transcription?"). Estimates (B, f0) robustly even from chords if the played notes are known. The companion parametric model uses only a **2-parameter B-vs-key model** (estimable from a few bass notes, constrained by string-design physics) plus a **4-parameter f0/tuning model**, fitting 5 pianos (Iowa, RWC ×3, MAPS) from single-note recordings. This is the single most valuable technique to adopt. Open PDF available via HAL (imt.hal.science/hal-00856735) and institut-langevin.espci.fr.

Extreme bass/high treble: partials are weak/sparse (bass: strong but few clean high partials due to hammer-node suppression and phantom partials; treble: very short decay, few partials, high B). Rigaud's physically-constrained B model helps precisely because it *interpolates* B across the keyboard rather than estimating each note independently; Shah & Välimäki (§6) address the treble specifically with a first-partial matching rule.

Cheap-mic/short-recording guidance: MAT/PFD work on short windows and consumer mics because they rely only on lower partials (which cheap mics capture well); EPT's own code explicitly boosts >5 kHz content to compensate for weak laptop/phone mic response above 5 kHz. Long (~20 s) recordings à la Hinrichsen are unnecessary for B — a ~1 s window post-attack suffices.

### 5. Machine learning / neural approaches

- **CREPE (Kim et al. 2018)**, **SPICE (Gfeller et al. 2020, self-supervised)**, **Basic Pitch (Spotify)** are monophonic/polyphonic f0 estimators. CREPE uses 360 pitch bins at 20-cent spacing (31–2006 Hz), Gaussian-blurred targets (σ=25 cents). Crucially these estimate **f0/pitch, not partial frequencies or B**, and their resolution (tens of cents) is coarse relative to the sub-cent precision tuning needs. For *isolated* piano notes, FFT peak-picking + quadratic interpolation + least-squares on the B-model is more accurate and far cheaper.
- **DDSP-piano (Renault, Mignot & Roebel 2022 DAFx; 2023 JAES 71(9):552–565)** and follow-ups (Differentiable Modal Synthesis, NeurIPS 2024; "Sine, Transient, Noise Neural Modeling of Piano Notes" 2024) use a **differentiable inharmonicity model**. Tellingly, DDSP-piano v2 estimates inharmonicity/detuning with a **signal-based extraction method from isolated notes** (i.e., classical, not a neural net) because "frequency estimation with differentiable oscillators is still an unsolved issue," and a "Deep-Inharmonicity" neural variant did not clearly beat the explicit model. This is direct evidence that, as of 2024–2026, **classical B estimation still wins** for this sub-task.
- **Commercial "AI" claims:** pianoscope Pro advertises "AI-driven curves"; CyberTuner advertises "AI-powered tunings"/"AI Concert Mode"; Verituner uses "dynamic" tuning. None publish a peer-reviewed or otherwise verifiable technical basis. CyberTuner's own App Store description makes the substantive claim explicit — its Smart Tune and Pitch Raise modes "use a US Patented expert system to individually predict every note on the piano… iRCT creates aural-quality tunings by directly matching sampled partials, just as concert aural tuners do" — i.e., a rule/interpolation-based expert system, not deep learning. pianoscope's own description is "thousands of calculations" optimizing user-selected pure intervals — classical constrained optimization. Treat "AI" here as marketing.

*Assessment:* Skip neural methods for analysis. The only defensible ML use would be robustness (e.g., peak/partial detection in noisy rooms), and even there classical methods suffice for a hobbyist tool.

### 6. Perceptual and psychoacoustic work

- **Octave stretching is genuinely perceptual, not just physical.** Jaatinen, Pätynen & Alho 2019 (JASA 146(5):3203–3214) measured subjective octave enlargement with real orchestral-instrument tones (N=36); the stretch grows toward higher frequencies and is near-flat below ~A2. Follow-ups (Acta Acustica 2021 on low-register uncertainty; EJN 2023 on late-stage cortical resolution of preferred octave size) reinforce this. There is also a competing brainstem-time-constant explanation (de Cheveigné et al., JASA 153(5):2600, 2023).
- **Inharmonic vs. harmonic tuning + the sympathetic-resonance question.** Jaatinen & Pätynen 2022 (JASA 152(2):1146–1157, "Effect of inharmonicity on pitch perception and subjective tuning of piano tones"): "The inharmonicity of all individual strings was measured on a Steinway D grand piano… Fifteen piano tuners and 18 orchestra musicians participated in the experiments." Two findings matter for you: (a) inharmonic tones produce a Railsback-like curve matching the subjective octave-enlargement curve; (b) the study explicitly investigated "the influence of strings of other piano keys on the measured inharmonicity of a single piano string" and found **"the covibrating strings of the other keys did not exhibit any meaningful effect on the measured inharmonicity of a single string"** — i.e., sympathetic-resonance contamination of B measurement is negligible, so elaborate muting is not required for B estimation (though it still matters for clean partial amplitudes).
- **Are Hinrichsen's per-note fluctuations a real fingerprint or optimizer noise?** Hinrichsen claimed the irregular note-to-note fluctuations correlate with an aural tuner's, calling them possibly essential. This is **unreplicated and weakly evidenced** (n=1 piano, non-reproducible optimizer). Szwajcowski & Pilch's whole motivation — that the original results weren't repeatable — casts doubt on treating the fluctuations as a deterministic fingerprint. Menrath (KUG) and piano technicians he interviewed consider the nondeterminism a defect. Treat the "fingerprint" claim as intriguing but unproven; do not architect around reproducing it.

### 7. Alternative objective functions

- **Sensory dissonance (Plomp-Levelt / Sethares).** Giordano 2015 (JASA 138(4):2359–2366) computes pairwise partial dissonance using Plomp-Levelt curves and Sethares' parametrization, sums it, and shows the minimum-dissonance tuning **reproduces the Railsback stretch** — a strong result that rivals entropy. Sethares' model (from *Tuning, Timbre, Spectrum, Scale*, 2005): R ∝ e^(−b1·s·Δf) − e^(−b2·s·Δf), with b1=3.5, b2=5.75, s = s0/(s1·min(f1,f2)+s2), s0=0.24, s1=0.021, s2=19 — directly codeable. Menrath (KUG 2021) extends this with **roughness + fluctuation strength** (peak sensitivity ~4 Hz, Zwicker-Fastl) and finds octave-by-octave minima broadly track the professional tuning.
- **Beat-rate / interval models.** Tuovinen, Hu & Välimäki 2019's CRI (Connected Reference Interval) process computes target f0 from weighted beat rates over multiple intervals (octaves, fifths, tenths, seventeenths, double octaves); per its abstract, "a tuning close to that of a professional tuner is achieved with a deviation of 2.5 cents (RMS) between the keys A0 and G5 and 8.1 cents (RMS) between G#5 and C8, where the tuner's results are not very consistent." Shah & Välimäki 2020 found, via listening test, that for **high tones the best simple rule is 2:1 partial matching** (upper tone's first partial = lower tone's second partial), beating three alternatives.
- **Information-theoretic variants.** Beyond Shannon entropy of the summed spectrum, no peer-reviewed work has systematically compared **KL divergence or mutual information between spectra** for piano tuning; Hinrichsen tried Gaussian jnd-smoothing and reported no improvement. This is under-explored.

Head-to-head comparisons that actually exist: Szwajcowski & Pilch (entropy vs. autocorrelation vs. aural vs. base-frequency, via listening test); ENTROTUNER (PSO vs. SA vs. quantized-Hinrichsen on entropy; entropy vs. physical-model method); Giordano (dissonance vs. measured Railsback); Shah & Välimäki (four high-tone rules). There is **no single study** cleanly comparing entropy vs. sensory-dissonance vs. beat-rate on the *same* piano with blind listening — a real gap.

### 8. Open-source implementations and licensing

- **Entropy Piano Tuner** — gitlab.com/tp3/Entropy-Piano-Tuner (mirror: github.com/levush/Entropy-Piano-Tuner; also SmallSharky/entropy-piano-tuner). C++/Qt (now Qt6-buildable per FreeBSD porting threads). **License: GPLv3.** Maintenance: effectively abandoned but still compiles. *Licensing implication: reimplementing the algorithm from the papers (arXiv 1203.5101 is CC-BY) avoids GPL entirely; do not copy or closely translate the C++ source. Algorithms/math are not copyrightable, but verbatim structure/porting would create a derivative work.*
- **RobertBoganKang/piano_tuning** (GitHub) — Python; builds an inharmonicity model, removes inharmonicity via frequency-domain stretch, uses an entropy optimization; author notes long compute even with parallelism, and that the temperament file is copied from TuneLab (**copyright caveat — do not reuse that file**). Check its own license before borrowing code.
- **beiciliang/estimate-f0-inharmonicity** (GitHub) — Python; implements Rigaud-David-Daudet NMF (B, f0) estimation from an isolated note. Directly useful; verify license.
- **flaviostutz/piano-tuna** (GitHub) — iOS inharmonicity-based tuner.
- **lrenault/ddsp-piano** (GitHub) — TensorFlow DDSP piano synthesizer with an explicit inharmonicity module and a single-note partial-extraction script; useful reference for the extraction code, though heavyweight.
- No mature **Rust or Julia** piano-tuning project surfaced; this is greenfield.

*Assessment:* Your cleanest legal path is a from-scratch Python implementation reading the math from Hinrichsen (CC-BY), Rigaud (author PDF on institut-langevin/HAL), Tuovinen (open SMC PDF), and Menrath (open KUG PDF). beiciliang and ddsp-piano give reference implementations of B estimation you can study for correctness (subject to their licenses).

### 9. Practical implementation gotchas

- **Quantization step.** Hinrichsen binned at 1 cent and shifted pitches in ±1-cent integer steps. ENTROTUNER shows results differ with vs. without this quantization. For a Python build, decouple the *analysis* resolution (fine, sub-cent via interpolation) from the *optimization* step; don't let a coarse 1-cent grid create false plateaus/local minima. This is a primary cause of the non-reproducibility.
- **FFT/window size for bass.** A0 is 27.5 Hz; to resolve adjacent 1-cent bins near the fundamental you need long windows (Hinrichsen used ~20 s at 44.1 kHz). But long windows blur the decaying spectrum. Compromise: use a **constant-Q / log-frequency transform** (EPT uses 1200 bins/octave, ~20.6 Hz–~10.5 kHz ≈ 10,800 bins) or analyze bass with longer windows than treble. Don't use one FFT size for all 88 notes.
- **Partial tracking over the decay.** Amplitudes and even effective frequencies drift during decay (double decay, prompt vs. after-sound). Menrath cut the first 50 ms (treble) / 100 ms (bass) of attack transient, then analyzed 0.1–1 s windows (short in treble, long in bass). Use a steady mid-decay segment; avoid attack and the noisy tail.
- **False beats & double decay.** Individual strings can have false beats (twin partials from asymmetry); two-string/three-string unisons show double decay. Record/measure **single strings** where possible (mute the others) for clean B, even though Jaatinen showed sympathetic contamination is small.
- **Unison beating during measurement.** If you can't mute, unison beats corrupt partial-amplitude and frequency estimates; prefer the una-corda/single-string condition or gate to the fastest-decaying clean segment.
- **Sample rate / mic calibration.** 44.1/48 kHz is fine. Cheap mics roll off >5 kHz — EPT boosts high notes to compensate; you should either apply a mic-response correction or (better) rely on lower partials for B so calibration doesn't matter. Watch for DC offset and clipping at ff.
- **Computational cost of the entropy objective.** Summing ~10,800-bin spectra over 88 notes and recomputing H per candidate move is the bottleneck; Hinrichsen's Monte Carlo and RobertBoganKang both report long runtimes. Mitigations: incremental entropy updates (only the shifted note's bins change), coarse-to-fine, vectorized numpy, or — best — optimize the low-dimensional Rigaud parametric model instead of raw spectra.

### 10. Validation strategy

- **Synthetic ground truth.** Generate signals with known B and f0 (f_n = n·f0·√(1+Bn²)), add noise, and confirm your estimator recovers B — this is how Rauhala and Rigaud validated. Do this first; it isolates estimator bugs from real-recording messiness.
- **Reference datasets with usable piano notes:** **RWC** (3 grands), **MAPS** (upright + grand), **Iowa MIS**, and the **Kawai K18** free sample library used by Szwajcowski. Rigaud's supplementary material gives per-note (B, f0) for 5 pianos — a de facto benchmark.
- **Railsback comparison — use with caution.** Shah & Välimäki note automatic tunings are "usually assessed by comparing the Railsback curve," but this is a weak validator: many different tunings share similar smooth Railsback curves while differing audibly, and the Railsback average hides the very fluctuations Hinrichsen cared about. Use it as a sanity check, not proof of quality.
- **Blind listening tests** are the real validator: ITU-R BS.1116 (small impairments, used by Szwajcowski) or MUSHRA/BS.1534 with webMUSHRA (used by Shah & Välimäki, Renault). Render tunings on the same sample set (SFZ virtual instrument) to isolate the tuning variable.

## Recommendations

**Stage 1 — Build the classical core first (highest value, lowest risk).**
- Implement per-note (B, f0) estimation with **MAT or PFD** (numpy/scipy), validated on synthetic signals with known B, then on MAPS/RWC.
- Fit the **Rigaud 2-parameter B-model + 4-parameter tuning model**; this gives a smooth, reproducible base tuning curve from a handful of recorded notes. This alone is a usable tuner and sidesteps entropy's reproducibility problems.
- Architecture fits your stack cleanly: FastAPI endpoints for upload/analyze/tune; store per-piano note measurements, B-curve parameters, and tuning targets in Postgres via SQLAlchemy; keep DSP in a worker.

**Stage 2 — Add an objective-function refinement layer, made reproducible.**
- Implement entropy *and* Sethares-dissonance objectives over the **parametric model's low-dimensional space** (not raw summed spectra). Optimize with CMA-ES or L-BFGS/PSO (`pyswarms`/`cma`); on ~4–10 parameters these converge deterministically, eliminating Hinrichsen's local-minimum lottery.
- Add ENTROTUNER-style **explicit equal-temperament constraints** rather than relying on all-key summation to hold ET.
- Decouple analysis resolution (sub-cent) from optimization step; never quantize the search to 1 cent.

**Stage 3 — Treble and validation.**
- For the top octaves, implement Shah & Välimäki's **2:1 first-partial-matching rule** as a special case.
- Validate with a small **MUSHRA (webMUSHRA)** test rendering your tunings vs. a professional/aural reference on the same SFZ sample set.

**What to skip:** neural pitch/partial estimators; "AI curve" mimicry; reproducing Hinrichsen's per-note fluctuation "fingerprint"; porting the GPL C++ EPT.

**Benchmarks that would change the plan:**
- If synthetic-ground-truth B recovery error > ~2–3% or bass-note failures dominate → invest in NMF (Rigaud) or comb-filter estimation before anything else.
- If, in blind listening, entropy/dissonance refinement is not preferred over the plain Rigaud base curve → ship the base curve and drop Stage 2 as unjustified complexity.
- If you obtain the Szwajcowski full text and PSO converges only with large swarms/iterations on the raw objective → confirms the parametric-model approach and abandons raw-spectrum optimization.

## Caveats
- **Paywall gaps:** Exact PSO hyperparameters, convergence, runtime, and numeric listening-test results in Szwajcowski & Pilch (2020) are not in open sources; treat the qualitative summary as confirmed but the missing numbers as to-be-verified (contact AGH Kraków authors or use institutional ScienceDirect access).
- **n=1 and non-piano results:** Hinrichsen's original was tested on one piano; his "fluctuation fingerprint" is unreplicated. ENTROTUNER's headline improvements (0.341 bits, 47.8% tuning quality, 11 intervals) are for the **Aulos (a wind instrument)**, not a piano — don't transfer the numbers.
- **Objective-function disagreement is unresolved:** entropy, sensory dissonance, and beat-rate models each reproduce the Railsback curve, but no blind head-to-head on one piano exists. Which is "best" is genuinely open.
- **Railsback validation is unreliable** as a quality metric (Shah & Välimäki); prefer listening tests.
- **Marketing vs. evidence:** vendor "AI" claims (pianoscope Pro, CyberTuner) have no published technical basis; where documented, they are classical expert systems/constrained optimization, not ML.
- **Licensing:** EPT and possibly some GitHub ports are GPLv3; RobertBoganKang's repo bundles a TuneLab-copyright temperament file. Reimplement from papers (Hinrichsen is CC-BY) and verify every repo's license before reuse.
