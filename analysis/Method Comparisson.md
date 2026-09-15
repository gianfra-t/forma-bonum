
## Method comparisson - Some numbers and cases

How does this method compares with other construction methods out there? Even if we think only of the wing, or airfil-like shapes as the point of reference to answer this question, it is not as simple as one might expect to answer. Definitely not as simple as comparing strenght and Young modulus of the materials used in the comparables. 

First off, we need "hard" data on wings built on this size, just to begin answering the question of "is this method even suitable in terms of strength-to-weight". Then we can start comparing these known design points against our models and tests.

We're taking on the following main datapoints to judge this method so far:
- **Chanzy & Keane (2018)** [1]. The Southampton DECODE Mk IV, a glass-clad foam wing over SLS nylon ribs and a carbon spar. The only wing here that was actually weighed.
- **Keane, Sóbester & Scanlan (2017)** [2], §11.9. SPOTTER, from the same Southampton group and construction family. A very good book, where they present planform and a sandbag load test, but no wing mass or structures breakdown, sadly. But we do get the total weight.
- **Sonkar et al. (2024)** [3]. A fully composite, vacuum-bagged CFRP wing for a 12 kg hybrid VTOL, at 1097 g for the whole wing (≈ 549 g per panel). This figure is stated in the paper, from its laminate sizing table.

All these sources target aircraft sizes of similar MTOW ranges as where this method is supposed to be most useful. In fact, in the lower range of it. Only for two of them we have good data:

| | DECODE Mk IV [1] | SPOTTER [2] | Sonkar VTOL [3] | **mk2 (this project)** |
|---|---|---|---|---|
| Construction | glass-clad foam, SLS nylon ribs, carbon spar | 35 mm CFRP tube spar, foam core, glass/Mylar cover, SLS nylon ribs | moulded CFRP sandwich, vacuum bagged | PLA printed on end, 20 × 3 mm pultruded rods |
| MTOW | 15 kg | 30 kg | ~12 kg | 28.8 kg (design case) |
| Span | 2.95 m | 4.20 m | 2.6 m | 1.6 m |
| Chord | 0.33 m | 0.466 m MAC, rectangular | 0.325 m mean\* | 200 → 160 mm |
| Wing area | 0.91 m² | 1.957 m² | 0.845 m²\* | 0.288 m² |
| Aspect ratio | 9 | 9.0\* | 8 | 8.9 |
| Wing loading | 16.5 kg/m²\* | 16.4 kg/m² | 15 kg/m² | 100 kg/m² (design) |
| Limit load factor | 3.8 (wings designed to 5 g) | 3.8 | not published | — |
| **Wing mass, per panel** | **976 g**, weighed | not published | **~549 g**, stated in the paper | **~450 g**, as built (545 g in the definition) |
| Wing mass, whole wing | 1952 g | not published | 1097 g | ~900 g |
| Wing mass / MTOW | 13.0 % | — | 9.1 % | 3.1 % of the design case |
| Root bending moment per panel, 1 g, uniform lift | 54 N·m\* | 154 N·m\* | 38 N·m\* | 56.5 N·m ([cantilever test](tests/experiment-02/wing_load_failed.ipynb)) |
| Structural test | none (wind tunnel and flight only) | sandbag, ~100 kg per wing (≈ 6.7 g). "The foam parts of the wing failed before the carbon spar" | coupons only, flight tested | sections 02 + 03 held 18 kgf in 3-point bending ([joint test](tests/experiment-03/mk2_joint_test.ipynb)); half-wing cantilever test failed early ([cantilever test](tests/experiment-02/wing_load_failed.ipynb)) |

<sub>\* derived and assumed, not published: DECODE wing loading = MTOW / area; SPOTTER AR = b²/S; Sonkar area = b²/AR and mean chord = S/b. SPOTTER values are the book's concept design (Tables 11.14–11.17); the as-built aircraft is 3.92 m / 34.5 kg. mk2's 28.8 kg is its 0.288 m² at the 100 kg/m² design loading used in the [cantilever test](tests/experiment-02/wing_load_failed.ipynb). Root moments are M = (MTOW/2)·g·(b/2)/2, the same uniform-lift assumption as there, ignoring the fuselage.</sub>

This leads us to the mk2 build ([mk2 definition](definitions/mk2/), load tested in the [cantilever test](tests/experiment-02/wing_load_failed.ipynb)).
It is the intention to build a wing that can carry comparative loads at similar structure weights. And although the planform is smaller on our demo wing, it is still a realistic aircraft. 

Important note: For those paying attention to the demo wing definition, you may notice the wing loading is quite larger than what the design points have. This was a combination of ambitious expectations for the demo, and a restriction about the amount of material (filament, reinforcement) that was around at the time. 

Our build for the demo wing tells us the entiere half wing weighted around 450g. This "would" put the wing at the level of Sonkar et al. [3] (~549 g per panel), and half what is presented in Chanzy & Keane [1] for the DECODE Mk IV aircraft (976 g per panel), but at almost double the loads. It simply was very ambitious demo.

The point is not the mass per panel on its own. The intention is to show that, at least analytically, the mk2 wing would resist as much total load as these wings, and at a smaller weight. In bending. At its 100 kg/m² design loading a mk2 half wing carries 14.4 kg at 1 g, and its root sees 56.5 N·m ([cantilever test](tests/experiment-02/wing_load_failed.ipynb)): the same bending moment as a DECODE Mk IV panel at 1 g (54 N·m), on a 200 mm chord instead of 330 mm. Meaning that even if the demo failed, we have an extra half a kilo per panel, against a conventional foam wing, to play with plastic density and to add more rods, and this is still using PLA. 

Against a moulded CFRP wing like Sonkar's [3] that margin shrinks to about 100 g, but that comparison is not like for like either: Sonkar's aircraft is lighter (~12 kg MTOW) and its panel sees about two-thirds of mk2's root bending moment at 1 g (38 against 56.5 N·m). Its 549 g is also stated in the paper rather than weighed. So at least analytically, with a higher wing loading on a similar aircraft, it is looking in the right direction.

The analytical margin still has to be closed at ultimate load: mk2's first predicted failure is wall shear at 3.78 g (≈ 214 N·m) ([mk2 definition](definitions/mk2/)), against the 5 g (≈ 272 N·m) the DECODE wings were designed to [1]. That is where the difference in weight and the larger structure will probably make a difference.

#### Area scaling

Mass scale linearly with wing area in this method. As volume increases with chord size, internal infill can be removed with cuts and still hold the skin. And again, this is before going to a plastic that will have at least double the modulus of PLA.


The rods already carry most of the bending, so a stiffer plastic changes the bending picture little. Where it counts is the skin, which is where the initial wing failed: a thin printed skin is lost by buckling or wrinkling, and its buckling stress rises roughly in proportion to the plastic's modulus.

Adding rods is cheap and covers bending; a better plastic covers the skin and infill density. Neither requires large reworking the method.

<p align="center">
  <img src="imagenes/advanced_large_wing.png" alt="Circular infill cuts and bore wall on a large-chord section" width="40%">
  <br>
  <sub><i>Circular infill cuts and bore wall on a large-chord section</i></sub>
</p>

Just to get an idea of the weights without a very large redesign, scaling one of the root sections of the demo wing by 50%, and therefore approaching areas closer to those used in the references, brings that root panel to 194 g of plastic, probably ~220 g with rods included. The entire half-wing would then be closer to 1 kg, as expected (plastic weight calculated by the slicer).

Clearly the demo could not prove this is feasible but as the analysis in the [rods-only model](analysis/idealized_rods_only.ipynb) and the [cantilever test](tests/experiment-02/wing_load_failed.ipynb) showcases, and as the models tell us, it should be possible after a redisgn and choosing the final plastic, at comparative weights. At least, if we consider bending that is. 


### References

1. Chanzy, Q., Keane, A.J. (2018). *Analysis and experimental validation of morphing UAV wings*. The Aeronautical Journal 122 (1249), 390–408. [doi:10.1017/aer.2017.130](https://doi.org/10.1017/aer.2017.130). Open access. Table 1 (aircraft), Table 4 (wing masses). Table 4 gives masses per panel: the conclusions state the morphing wings "weigh only 54 g each more", and 1030 − 976 = 54.
2. Keane, A.J., Sóbester, A., Scanlan, J.P. (2017). *Small Unmanned Fixed-wing Aircraft Design: A Practical Approach*. Wiley. ISBN 978-1-119-40629-7. §11.9 "A Twin Tractor Design: SPOTTER" (Tables 11.14, 11.16, 11.17); Ch. 3, Fig. 3.5 (sandbag test).
3. Sonkar, S., Kumar, P., George, R.C., Yuvaraj, T.P., Philip, D., Ghosh, A.K. (2024). *Low-cost development of a fully composite fixed-wing hybrid VTOL UAV*. Journal of the Brazilian Society of Mechanical Sciences and Engineering 46 (4), 252. [doi:10.1007/s40430-024-04785-2](https://doi.org/10.1007/s40430-024-04785-2). Open access. Table 1 (aircraft), Table 4 (laminate trade study, wing weight).
