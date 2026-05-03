# `gct.owl` — Companion OWL serialization of the GCT schema

This file ships alongside the paper *The Tensegrity Knowledge Graph: A Holonic Architecture for Scientific Knowledge Representation* and operationalizes the BFO-alignment programme that §7.2 of the paper sketches. It is a first-pass OWL 2 serialization of the twelve-slot GCT schema, written in Turtle for readability, and parseable by `rdflib >= 6` (validated under `rdflib 7.6.0`: 240 triples, no parse errors).

## Slot-to-BFO mapping table

| GCT slot | OWL property in `gct.owl` | BFO 2.0 alignment | Notes |
|---|---|---|---|
| CAUSE | `gct:cause` | `subPropertyOf bfo:RO_0002411` (causally upstream of) | Direct match for efficient causation; transitive |
| EFFECT | `gct:effect` | `subPropertyOf bfo:RO_0002418` (causally downstream of) | Inverse of `gct:cause`; transitive |
| PREDECESSOR | `gct:predecessor` | `subPropertyOf bfo:BFO_0000062` (preceded by) | Temporal precedence; transitive |
| SUCCESSOR | `gct:successor` | `subPropertyOf bfo:BFO_0000063` (precedes) | Inverse of `gct:predecessor`; transitive |
| CONTAINER | `gct:container` | `subPropertyOf bfo:BFO_0000051` (has part) | Specialised: scale-strict (s(u) > s(v)) |
| INSTANTIATION | `gct:instantiation` | `subPropertyOf bfo:BFO_0000059` (concretizes) | Kept as first-class edge rather than `rdf:type` to preserve scale-indexed query semantics |
| SUBSTRATE | `gct:substrate` | `subPropertyOf bfo:RO_0000052` (inheres in) | Aristotelian material cause |
| SPECIFICATION | `gct:formallySpecifiedBy` | **NEW (no BFO analog)** | Aristotelian formal cause; closest BFO concept (IAO `is about`) is heavier than required |
| CODE | `gct:implementedBy` | **NEW (no BFO analog)** | Implementation grounding; BFO does not model code-substrate links to formal artefacts |
| PEER_COHERENT | `gct:peerCoherentWith` | **NEW (symmetric, no BFO analog)** | Same-scale coherence between information artefacts |
| PEER_CONTRADICTORY | `gct:peerContradicts` | **NEW (symmetric, no BFO analog)** | `propertyDisjointWith` `gct:peerCoherentWith` |
| THERMO | `gct:thermodynamicallyCoupledTo` | **NEW (symmetric, no BFO analog)** | Domain-specific to the Tensegrity programme |

Seven of twelve slots receive a defensible BFO mapping; the remaining five are deliberately introduced in the `gct:` namespace, with inline `rdfs:comment` annotations recording why no BFO subsumption was forced.

## Holonic scale class hierarchy

`gct:Holon ⊑ bfo:BFO_0000001 (entity)`. Five sibling subclasses correspond to the five holonic scales of Definition 2 of the paper:

- `gct:HolonScale0` — byte level
- `gct:HolonScale1` — word level (most experiments live here)
- `gct:HolonScale2` — sentence / paper-section / hypothesis level
- `gct:HolonScale3` — whole-paper level
- `gct:HolonScale4` — corpus / programme level

The five sibling classes are declared `owl:AllDisjointClasses`. The functional data property `gct:hasScale` (range: `xsd:integer` restricted to 0..4) records the scale per holon at the data level, redundantly with the class assertion, to support both class-based and value-based queries. Two further data properties operationalize Definitions 4–5: `gct:veScore` (xsd:decimal) for the harmonic VE score, and `gct:aristotelianCompleteness` (xsd:decimal restricted to [0.0, 1.0]) for AC(n).

## Worked example (in plain English)

The file declares five individuals demonstrating end-to-end schema use, modelled on real Tensegrity D-IDs:

1. **`:experiment_d101`** — instance of `gct:Experiment` and `gct:HolonScale1`, with `gct:hasScale 1`, `gct:aristotelianCompleteness 0.75`, `gct:veScore 0.83`, and a 2026-04-14 timestamp. Represents the canonical HNC equiangularity experiment.
2. **`:protocol_p_a2`** — instance of `gct:Specification` and `gct:HolonScale2`, representing the OSF pre-registration P-A2 that fixes the form of D-101.
3. The **SPECIFICATION edge** between them: `:experiment_d101 gct:formallySpecifiedBy :protocol_p_a2 .` — D-101's design conforms to the pre-registration's formal cause.
4. **`:experiment_d099`** — a second experiment (the K=4 ETF baseline) that ran earlier; the lineage edge `:experiment_d101 gct:predecessor :experiment_d099` records that D-101 follows D-099 in time, and the symmetric `:experiment_d099 gct:peerCoherentWith :experiment_d101` records that the two confirm each other at the same holonic scale.
5. **`:paper_section_p1_intro`** — the introduction of paper P1 at scale 2; it `gct:cause`s D-101 (the section's research motivation efficient-caused the experiment's design) and `gct:container`s D-101 (the section also contains the experiment by reference).

## OWL profile

The ontology targets **OWL 2 DL**. All constructs used — `owl:ObjectProperty`, `owl:DatatypeProperty`, `owl:FunctionalProperty`, `owl:TransitiveProperty`, `owl:SymmetricProperty`, `owl:inverseOf`, `owl:propertyDisjointWith`, `owl:AllDisjointClasses`, datatype restrictions via `rdfs:Datatype` + `owl:onDatatype` + `owl:withRestrictions` — are within the OWL 2 DL profile. No metamodelling, no property chains over inverses-of-functional-properties, no punning. A reasoner such as HermiT or ELK should accept the file without DL-violation warnings.

## BFO 2.0 reference

The canonical BFO 2.0 (2020 Common Logic and OWL release) specification: <https://github.com/BFO-ontology/BFO-2020>. The OBO-Foundry IRI prefix is `http://purl.obolibrary.org/obo/`. BFO IRIs in this file are stub-declared rather than fully imported; consumers wishing strict alignment should additionally `owl:imports <http://purl.obolibrary.org/obo/bfo.owl>`.

## Validation

```bash
pip install rdflib
python -c "from rdflib import Graph; g = Graph(); g.parse('gct.owl', format='turtle'); print(len(g), 'triples')"
# -> 240 triples
```

All twelve slots, all five scale classes, all four data properties, and all five worked-example individuals are present and resolvable. The file is intended as a starting point for full BFO/OBO-Foundry alignment, not as the final published ontology — see paper §7.2 and §8 for the full integration roadmap.
