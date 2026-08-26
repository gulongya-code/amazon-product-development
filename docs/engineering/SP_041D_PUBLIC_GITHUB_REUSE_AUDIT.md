# TASK-SP-041D Public GitHub Reuse and License Audit

- Audit date: 2026-08-26
- Required baseline: `bcefe61e8bbd1a253663eece60a234b124a3f111`
- Audit timing: completed before route-discovery implementation
- Final reuse disposition: `NO_EXTERNAL_COPY_SELECTED`

## Search scope

Public GitHub was searched for categorical clustering, k-modes/k-medoids, Jaccard or Hamming distance, concentration/HHI metrics, reconstructed aggregate growth, diversity selection, and cluster-stability techniques. The audit considered semantic fit, determinism, explainability, dependency cost, maintenance maturity, and license.

## Candidates

| Candidate | License observed | Decision | Reason |
| --- | --- | --- | --- |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn) | BSD-3-Clause | Reference only; reject dependency | Mature clustering and validation library, but numeric clustering and adjusted-rand machinery do not match governed categorical route membership. NumPy/SciPy dependency cost and canonical cluster-label handling add complexity with no benefit over deterministic structural signatures. |
| [kmodes](https://github.com/nicodv/kmodes) | MIT | Reference only; reject dependency | K-modes/k-prototypes are relevant to categorical data, but require a chosen `k`, initialization/canonicalization policy, and NumPy. Missing-value treatment and probabilistic/initialization behavior are less explainable than exact governed attribute signatures. |
| [scikit-learn-extra](https://github.com/scikit-learn-contrib/scikit-learn-extra) | BSD-3-Clause | Reference only; reject dependency | K-medoids introduces scikit-learn/NumPy dependencies and medoid concepts. Selecting representatives is expressly reserved for SP-041E, so this would also risk scope leakage. |
| [SciPy distance functions](https://github.com/scipy/scipy/blob/main/scipy/spatial/distance.py) | BSD-3-Clause | Reference only; reject dependency | Jaccard/Hamming formulas are straightforward for the bounded governed structural descriptors and do not justify a new scientific-computing dependency. |
| [open-risk/concentrationMetrics](https://github.com/open-risk/concentrationMetrics) | MIT | Reference only; reject dependency | HHI/top-N concentration formulas are small deterministic Decimal aggregations. Copying or adding a package would be less maintainable than a documented project-local formula. |
| [scikit-learn adjusted-rand implementation](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/metrics/cluster/_supervised.py) | BSD-3-Clause | Reference only; reject dependency | Permutation stability can be asserted by comparing deterministic membership identities directly; a statistical agreement dependency is unnecessary. |
| Public MMR/diversity snippets and small repositories | Mixed or unclear | Reject | Several snippets have absent or unclear licensing. SP-041D will use an independently written, documented greedy minimum structural-distance rule, not copied MMR code. |

## Chosen implementation boundary

SP-041D will use only the Python standard library and dependencies already required by the repository. The project-specific implementation will comprise:

- deterministic exact grouping by versioned, non-cosmetic structural-attribute signatures;
- fail-closed handling for insufficient known attributes, conflicts, review-required records, singletons, and noise;
- Decimal-based share, reconstructed-growth, top-N concentration, HHI, percentile, and efficiency calculations;
- deterministic candidate ordering plus a configured greedy minimum structural-distance diversity constraint;
- direct reuse of repository contracts for evidence, availability, coverage, provenance, and identity.

No external source code, model weights, data, test vectors, or generated artifacts will be copied. No new attribution file or dependency-license notice is required. The repository's existing dependency and notice posture remains unchanged.

## License conclusion

All reviewed candidates have either a permissive license or unclear licensing, but none is selected for incorporation. Public implementations informed only the high-level build-versus-reuse decision. SP-041D's algorithms and tests will be independently authored against the GitHub Issue contract and existing repository conventions.

## Exact search queries

1. `GitHub scikit-learn clustering BSD-3-Clause LICENSE KMeans agglomerative clustering`
2. `GitHub nicodv kmodes k-prototypes LICENSE`
3. `GitHub scikit-learn-contrib scikit-learn-extra KMedoids LICENSE`
4. `GitHub categorical Jaccard Hamming clustering Python LICENSE`
5. `GitHub Python HHI concentration metric implementation license`
6. `GitHub weighted aggregate growth reconstruct prior current growth rate Python license`
7. `GitHub maximal marginal relevance MMR diversity selection Python license`
8. `GitHub cluster stability adjusted rand score scikit-learn license`

## Project-semantic test protection

The SP-041D suite protects the independently authored boundary with cross-category exact-signature discovery, color exclusion, strict configuration, input/runtime permutation stability, singleton/conflict/insufficient-evidence behavior, listing and available-sales share invariants, missing-sales exclusion, reconstructed aggregate growth including `g <= -1`, missing-age treatment, percentile/concentration/adoption coverage, deterministic 3?5 candidate selection, diversity suppression, and sanitized full-chain CLI diagnostics.
