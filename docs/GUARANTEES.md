# Register of guarantees

Each row is one promise the package makes, the file that keeps it, and the
tests that check it. `tests/unit/test_guarantees.py` fails if a row cites a
test or a file that does not exist, or cites no test. A new promise in the
README, the API or the contract gets a row here, with a test, in the same
change. Where a test checks only some cases of a general rule, the row says
so. Promises that are stated in the documentation but not yet checked by a
test are listed at the end; they are not hidden.

What these guarantees rest on, and what they do not prove, is stated in
[CONTRACT.md](CONTRACT.md) (last section): validity is conditional on the
analytic proofs of the Letter and its archive, on the provisional proofs of
[PROOFS.md](PROOFS.md), on Arb/Acb, and on IEEE arithmetic.

Tests are written `file::function`, relative to `tests/`.

## Integrity of the data

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G01 | Every bank and the manifest are checked against their SHA-256 digest before any deserialization; a mismatch raises `IntegrityError`. Every read is verified, whether or not it comes after `clear_cache()`. | `src/certoutage/_banks.py` | `unit/test_contracts.py::test_integrity_check_precedes_deserialization`, `unit/test_release.py::test_corrupted_final_certificate_is_rejected_before_json_loading` |
| G02 | A changed bank or manifest never produces a result or a decision. | `src/certoutage/_banks.py` | `unit/test_release.py::test_hash_mismatch_stops_certified_calculations` |
| G03 | Object arrays are never unpickled (`allow_pickle=False`). | `src/certoutage/_banks.py` | `unit/test_runtime_guarantees.py::test_object_arrays_are_never_unpickled` |
| G04 | Loaded bank arrays are read-only. A repeated query (same model, same precision) is answered without reading the banks again, and `clear_cache()` forces them to be read and verified again. Other queries may read banks again; each such read is verified (G01). | `src/certoutage/_banks.py`, `src/certoutage/_runtime.py`, `src/certoutage/api.py` | `unit/test_runtime_guarantees.py::test_loaded_bank_arrays_are_read_only`, `unit/test_runtime_guarantees.py::test_banks_are_not_read_again_until_clear_cache` |
| G05 | Queries make no network access. Tested on outage, floor, dimensioning, comparisons and both J_max branches, with provided and generated environments. | `src/certoutage/_banks.py` | `unit/test_runtime_guarantees.py::test_queries_make_no_network_access` |
| G06 | Queries write no file, and the banks are never rewritten. Same queries as G05. | `src/certoutage/_banks.py`, `src/certoutage/_runtime.py` | `unit/test_runtime_guarantees.py::test_queries_write_no_file` |
| G07 | `tools/regenerate_ppp.py` never overwrites an existing file. `tools/regenerate_from_archive.py` refuses an output inside the archive and an existing output directory. | `tools/regenerate_ppp.py`, `tools/regenerate_from_archive.py` | `unit/test_runtime_guarantees.py::test_regeneration_tools_refuse_unsafe_outputs` |
| G08 | The contract of a result records the name and verified SHA-256 digest of every bank read, and `analytic` when no bank is used. | `src/certoutage/api.py` | `unit/test_runtime_guarantees.py::test_contract_records_the_verified_digests_of_the_banks_read`, `unit/test_contracts.py::test_context_is_restored_and_provenance_visible` |

## Scope and inputs

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G09 | A model outside the documented scope raises `ValueError`. It is never answered `inconclusive` and never rounded to a supported case. | `src/certoutage/models.py` | `unit/test_contracts.py::test_invalid_models` |
| G10 | Decimal parameters reject booleans, NaN and infinities. Link coefficients also accept exact rationals and the specified infeasible-allocation infinity (G46). | `src/certoutage/models.py` | `unit/test_contracts.py::test_invalid_models`, `unit/test_runtime_guarantees.py::test_infinite_or_nan_parameters_are_rejected`, `unit/test_audit_fable.py::test_m5_float32_is_read_by_decimal_string_and_selects_archive` |
| G11 | The SNR is finite, numeric (not a boolean), in dB, within [-1000, 1000]; the target is in (0, 1). | `src/certoutage/api.py` | `unit/test_contracts.py::test_invalid_queries`, `unit/test_runtime_guarantees.py::test_out_of_range_or_non_numeric_snr_is_rejected`, `unit/test_contracts.py::test_invalid_targets` |
| G12 | `Numerics` accepts integer precisions from 160 to 1024 bits, integer DFT powers from 12 to 20, and only the documented bank policies. | `src/certoutage/models.py` | `unit/test_contracts.py::test_grid_and_numerics_validation`, `unit/test_runtime_guarantees.py::test_numerics_upper_bounds_and_types` |
| G13 | The SNR grid is exact: multiples of 1/128 dB, validated in rationals, independent of the `decimal` context. | `src/certoutage/models.py` | `unit/test_contracts.py::test_grid_and_numerics_validation`, `unit/test_audit_fable.py::test_m1_rejects_fable_grid_under_low_decimal_precision`, `unit/test_audit_fable.py::test_m1_exact_grid_is_used_with_decimal_rounding_trapped` |
| G14 | No bank is chosen by rounding: an intensity that is not exactly an archived one is generated afresh. | `src/certoutage/_runtime.py` | `unit/test_contracts.py::test_almost_archived_intensity_does_not_select_wrong_bank`, `unit/test_audit_fable.py::test_m5_float32_is_read_by_decimal_string_and_selects_archive` |
| G15 | The Chernoff comparator outside its covered cases raises `ValueError` (tested: m=2). | `src/certoutage/api.py` | `unit/test_contracts.py::test_chernoff_cannot_exclude_outage` |

## Certified quantities

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G16 | The archived numerical results are reproduced bit for bit (the link contract fields added in G53 are checked separately): central claims, Gamma comparisons, Table I, Figure 1, the twenty Nakagami cases and Table II. | `src/certoutage/api.py`, `src/certoutage/_runtime.py` | `regression/test_central.py::test_all_raw_points_and_decisions`, `regression/test_central.py::test_gamma_all_raw_floors_and_thresholds`, `regression/test_extended.py::test_table_i_all_endpoints`, `regression/test_extended.py::test_figure_1_eight_sizes`, `regression/test_extended.py::test_nakagami_twenty_cases`, `regression/test_table_ii_example.py::test_table_ii_example_is_bit_identical` |
| G17 | Every result is a valid probability interval: finite, 0 ≤ lower ≤ upper ≤ 1, otherwise `ArithmeticError`. | `src/certoutage/models.py` | `unit/test_runtime_guarantees.py::test_enclosures_are_valid_probability_intervals` |
| G18 | For finite d, the floor is exactly zero in C-INR and with λ=0. Outage enclosures are monotone in the SNR (tested on four SNR values, C-INR, user 2, provided banks). | `src/certoutage/api.py` | `unit/test_contracts.py::test_monotonicity_and_zero_floor` |
| G19 | A new intensity or a configurable M keeps the proof. If the Fourier remainder exceeds 1, the CDF bounds are the explicit coarse certificate [0, 1] with the analytic tail, never an extrapolation (tested at λ=1e-500). | `src/certoutage/_generate.py` | `regression/test_new_environment.py::test_new_intensity_and_two_precisions`, `regression/test_new_environment.py::test_new_gamma_and_largest_distribution`, `unit/test_contracts.py::test_tiny_intensity_returns_valid_coarse_enclosure` |
| G20 | After PPP generation, the envelopes are checked against the Laplace transform at s = 0.1, 0.5 and 1; an inconsistency raises `ArithmeticError`. | `src/certoutage/_generate.py` | `unit/test_audit_fable.py::test_m3_generated_ppp_checks_all_archive_laplace_points`, `unit/test_audit_fable.py::test_m3_laplace_guard_rejects_inconsistent_inversion` |
| G21 | The nine vendored guards, the Laplace check and input validation hold under `python -O`. | `src/certoutage/_vendor/commun.py`, `src/certoutage/_vendor/ppp.py`, `src/certoutage/_vendor/thermal_backend.py`, `src/certoutage/_generate.py`, `src/certoutage/models.py` | `unit/test_runtime_guarantees.py::test_guards_hold_under_python_optimization`, `unit/test_audit_fable.py::test_m4_nonfinite_balls_raise_arithmetic_error`, `unit/test_audit_fable.py::test_m4_inward_transport_is_rejected`, `unit/test_audit_fable.py::test_m4_inconsistent_cdf_envelopes_are_rejected`, `unit/test_audit_fable.py::test_m4_negative_masses_are_rejected`, `unit/test_audit_fable.py::test_m4_tighten_rejects_crossed_bounds`, `unit/test_audit_fable.py::test_m4_series_and_poisson_preconditions_survive_optimization` |
| G22 | No `assert` statement lies on a path reachable from the public API. The two left in `_vendor/oracles.py` are in archive code that the package never runs. | `src/certoutage/_runtime.py` | `unit/test_runtime_guarantees.py::test_no_assert_is_reachable_from_the_public_api` |
| G23 | The stored CDF bound at B is conservative (previous node in the DFT branch). | `src/certoutage/_generate.py` | `unit/test_audit_fable.py::test_m6_dft_endpoint_is_conservative_previous_node` |

## Decisions

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G24 | `excluded` is returned only when the floor's lower bound is strictly above the target; an exhausted grid gives `inconclusive`. The "only when" holds by construction of the decision rule; it is tested on one exhausted grid and on the archived decisions. | `src/certoutage/api.py` | `unit/test_contracts.py::test_finite_grid_never_excludes_every_snr`, `regression/test_central.py::test_all_raw_points_and_decisions` |
| G25 | Left censoring gives `feasible` with -∞ as the lower edge; no finite edge is invented. | `src/certoutage/api.py` | `unit/test_contracts.py::test_censored_left_is_feasible_without_invented_lower` |
| G26 | The Chernoff comparator never yields `excluded` for the physical model. This holds by construction of the decision rule; it is tested on N=20. | `src/certoutage/api.py` | `unit/test_contracts.py::test_chernoff_cannot_exclude_outage` |
| G27 | `threshold_difference` refuses censored decisions, a missing or different target, a missing parameter, and a different user, convention, N, m, λ or η. It accepts equivalent decimal spellings and different comparators. | `src/certoutage/api.py` | `unit/test_audit_fable.py::test_m7_refuses_incomparable_thresholds`, `unit/test_runtime_guarantees.py::test_threshold_difference_refuses_other_physical_parameters`, `unit/test_runtime_guarantees.py::test_threshold_difference_refuses_missing_target_or_parameters`, `unit/test_audit_fable.py::test_m7_equivalent_targets_and_distinct_comparators_remain_comparable`, `unit/test_contracts.py::test_censored_left_is_feasible_without_invented_lower` |
| G28 | The `falsely feasible` and `masked` diagnostics are derived from the statuses (tested on the Table II example). | `src/certoutage/api.py` | `regression/test_central.py::test_table_ii_displays_and_diagnostics` |
| G29 | The J_max result is a floor lower bound: its upper edge is not an upper bound on the PPP floor; in C-INR its limit for finite d is zero and labelled as such. | `src/certoutage/api.py` | `unit/test_contracts.py::test_central_largest_bound_is_not_a_ppp_upper_bound`, `unit/test_contracts.py::test_largest_inr_limit_is_labelled_correctly` |
| G30 | A provided certificate reports `precision_bits=160`, whatever precision was requested. This holds by construction; it is tested at 512 bits. | `src/certoutage/api.py` | `unit/test_audit_fable.py::test_m6_stored_certificate_reports_its_actual_precision` |

## Display and arithmetic context

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G31 | Displayed values (`Enclosure.format`, `ThresholdDifference.format`) are rounded outward, through exact rationals, independently of the `decimal` context and its traps. | `src/certoutage/models.py` | `unit/test_contracts.py::test_rounding_is_outward`, `unit/test_contracts.py::test_threshold_display_on_fine_grid_is_outward`, `unit/test_audit_fable.py::test_m2_fable_quotients_round_outwards`, `unit/test_audit_fable.py::test_m2_large_quotient_and_exact_boundary`, `unit/test_runtime_guarantees.py::test_display_of_threshold_differences_ignores_decimal_traps`, `regression/test_central.py::test_signs_display`, `regression/test_central.py::test_floor_and_decisive_displays` |
| G32 | The global Arb context (precision and threads) is restored after each Arb computation of the package, including after an exception; the precision used is recorded in the contract. | `src/certoutage/_runtime.py` | `unit/test_contracts.py::test_context_is_restored_and_provenance_visible`, `unit/test_runtime_guarantees.py::test_arb_context_is_restored_after_an_exception` |
| G33 | Every Arb computation of the package runs under one lock. Validation, display and `threshold_difference` do not need it and run outside. This holds by construction (every public entry computes inside `rt.arithmetic`); it is tested on one `outage_enclosure` call. | `src/certoutage/_runtime.py` | `unit/test_runtime_guarantees.py::test_calls_are_serialized_by_one_lock` |

## Release metadata

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G34 | The version and release date agree across the package, CITATION.cff, codemeta.json, the changelog and the README (every "version X.Y.Z" and the citation date); the python-flint version quoted in the README is the pinned one. | `CITATION.cff`, `CHANGELOG.md`, `README.md` | `unit/test_release.py::test_release_versions_and_dates_agree`, `unit/test_release.py::test_readme_quotes_the_package_version` |

## Caches

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G35 | A PPP or Gamma environment is reused only for the same intensity, path-loss exponent, interference model, DFT size M, precision and bank policy; any change in one of these builds a new one, and it is built at the precision of its key, otherwise `ArithmeticError`. N, m, the convention, the user and the gain do not rebuild it, and sharing changes no result. Tested at M = 2^12 on seven sharing cases and seven key changes. | `src/certoutage/_runtime.py` | `unit/test_runtime_guarantees.py::test_environment_is_shared_across_n_m_convention_user_and_gain`, `unit/test_runtime_guarantees.py::test_environment_is_rebuilt_when_its_key_changes` |

## Interval engine and dependencies

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G36 | The contract of every result names the python-flint version actually imported, read at run time; python-flint is pinned exactly, and the pin, `codemeta.json` and the imported version agree (dependency policy in CONTRIBUTING.md). The first part holds by construction (no code passes the field explicitly); it is tested on `outage_enclosure` and `floor`. The field names the Python binding, not the FLINT C library. | `src/certoutage/models.py`, `pyproject.toml` | `unit/test_release.py::test_contract_names_the_interval_engine_actually_imported`, `unit/test_release.py::test_declared_dependency_matches_the_imported_engine` |

## Provenance of the extracted code

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G37 | In `docs/EXTRACTION.json`, every destination file whose bytes differ from 0.1.0 carries `post_release_sha256`, and every recorded digest, of 0.1.0 or later, is that of the file it names. | `docs/EXTRACTION.json` | `unit/test_release.py::test_extraction_inventory_matches_the_files` |

## Internal bank store

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G38 | Generated banks, like embedded banks, are verified before loading: exact descriptor schema, identity derived from parameters and generator, SHA-256 and byte count. Invalid data, or a directory in place of a bank or descriptor, raises `IntegrityError`, never a result or fallback; an unreadable file raises the operating system's `PermissionError`. | `src/certoutage/_banks.py` | `unit/test_bank_store.py::test_generated_corruption_is_rejected_before_loading`, `unit/test_bank_store.py::test_descriptor_tampering_is_rejected`, `unit/test_bank_store.py::test_descriptor_fields_are_exact`, `unit/test_bank_store.py::test_unreadable_descriptors_are_integrity_errors`, `unit/test_bank_store.py::test_generated_integrity_error_is_not_transformed`, `unit/test_bank_store.py::test_directory_in_place_of_bank_or_descriptor_is_an_integrity_error` |
| G39 | The cache never shadows an embedded bank. Generated names are disjoint from all 43 embedded names; the central Eq. (3) + mean case retains bit-identical bounds and its full contract despite shadow files. | `src/certoutage/_banks.py` | `unit/test_bank_store.py::test_cache_never_shadows_embedded_banks`, `unit/test_bank_store.py::test_embedded_resolution_does_not_even_consult_cache`, `unit/test_bank_store.py::test_generated_names_are_disjoint_from_all_embedded_names` |
| G40 | No store writes without an explicit internal writer call; imports and reads create no directory. Cache environment variables are read at each call, with absolute XDG paths and HOME/USERPROFILE fallback. All store tests block network sockets (including spawned writers). | `src/certoutage/_banks.py` | `unit/test_bank_store.py::test_import_creates_no_cache`, `unit/test_bank_store.py::test_cache_location_and_reads_create_no_directories`, `unit/test_bank_store.py::test_cache_environment_is_read_on_every_call`, `unit/test_bank_store.py::test_generated_round_trip_and_descriptor`, `unit/test_bank_store.py::test_four_spawn_writers_leave_one_verified_pair` |
| G41 | A missing generated bank or descriptor, or a file in place of the cache's `generated` directory, raises named `BankNotAvailable(LookupError)` with the cache location and preparation hint, never a fallback; no absence or generated descriptor is cached. | `src/certoutage/_banks.py` | `unit/test_bank_store.py::test_absent_generated_bank_never_falls_back`, `unit/test_bank_store.py::test_absence_and_descriptor_reads_are_not_cached`, `unit/test_bank_store.py::test_cache_that_is_a_file_means_absent_bank` |
| G42 | Generated identities use canonical exact flat parameters and generator name/version; floats and nested values are refused. Array keys match `[A-Za-z0-9_]{1,64}`. NPZ serialization is deterministic, the writer checks that its bytes decode to the requested arrays, object dtypes are refused, and loaded arrays are read-only. | `src/certoutage/_banks.py` | `unit/test_bank_store.py::test_generated_identity_is_canonical_and_versioned`, `unit/test_bank_store.py::test_inexact_or_nested_parameters_are_rejected`, `unit/test_bank_store.py::test_serialization_is_deterministic_across_zip_timestamps`, `unit/test_bank_store.py::test_object_dtype_is_refused_before_any_write`, `unit/test_bank_store.py::test_generated_round_trip_and_descriptor`, `unit/test_bank_store.py::test_array_keys_are_restricted_before_any_write`, `unit/test_bank_store.py::test_serialized_bytes_must_reproduce_their_arrays` |
| G43 | A stored bank whose arrays (keys, dtype, shape, bytes) differ from the requested ones under the same identity makes the writer raise `IntegrityError` and is left untouched. Writes commit the bank before its descriptor, leave a verified pair with equal arrays untouched and clean temporary files on failure while preserving the original exception. Four concurrent deterministic writers leave a verified pair. Windows replacement retries are bounded; read-only cache reads work (POSIX permission test skipped on Windows and for root). | `src/certoutage/_banks.py` | `unit/test_bank_store.py::test_bank_is_committed_before_its_descriptor`, `unit/test_bank_store.py::test_verified_existing_bank_is_not_rewritten`, `unit/test_bank_store.py::test_failed_replace_cleans_temporary_and_preserves_exception`, `unit/test_bank_store.py::test_failed_flush_cleans_temporary`, `unit/test_bank_store.py::test_four_spawn_writers_leave_one_verified_pair`, `unit/test_bank_store.py::test_replace_retry_is_bounded_and_windows_only`, `unit/test_bank_store.py::test_read_only_cache_can_be_read_but_not_written`, `unit/test_bank_store.py::test_writer_refuses_different_arrays_under_the_same_identity`, `unit/test_bank_store.py::test_writer_accepts_equal_arrays_in_another_memory_layout` |
| G44 | The reserved fetched origin raises `NotImplementedError` and creates no cache directory. No current public query produces `generated-banks`; the exception for missing generated banks stays internal: the public modules use only `arrays`, `manifest`, `receipt`, `verified_bytes` and `IntegrityError` from `_banks`, and representative public queries resolve embedded names only. | `src/certoutage/_banks.py`, `src/certoutage/models.py`, `src/certoutage/__init__.py` | `unit/test_bank_store.py::test_no_public_path_reaches_the_generated_store`, `unit/test_bank_store.py::test_fetched_origin_is_explicitly_reserved`, `unit/test_bank_store.py::test_generated_names_are_disjoint_from_all_embedded_names`, `unit/test_bank_store.py::test_cache_never_shadows_embedded_banks`, `unit/test_runtime_guarantees.py::test_contract_records_the_verified_digests_of_the_banks_read` |

The generated-bank threat model covers corruption, truncation, interrupted
writes, process races and a changed generator name or version. A generator
whose code changes under the same name and version is caught only when the
writer is asked to store different arrays (G43), not at read time; the
optional `code_sha256` is recorded, not checked. Local descriptors do not
authenticate data against an adversary who rewrites both bank and descriptor.
They do not prove mathematical correctness. The future fetched origin will
use digests pinned in code; it is not implemented in this version.

## Link coefficients and interference gain (unreleased, 0.3.0)

| ID | Guarantee | Kept by | Tests |
|---|---|---|---|
| G45 | The Letter defaults equal Model.from_link(); explicit equivalent defaults preserve the raw binary64 bounds on the sampled bank and direct cases, and the existing numerical regressions remain unchanged. | `src/certoutage/models.py`, `src/certoutage/api.py`, `src/certoutage/_runtime.py` | `unit/test_link_parameters.py::test_defaults_are_the_letter`, `unit/test_link_parameters.py::test_explicit_defaults_preserve_hex` |
| G46 | d1, d2 and g are validated exactly and stored as reduced rational strings; only d accepts the specified infinity. from_link computes the two-threshold SIC maximum with exact positive inputs, independently of the decimal context. | `src/certoutage/models.py` | `unit/test_link_parameters.py::test_equivalent_inputs_are_canonical`, `unit/test_link_parameters.py::test_invalid_coefficients_raise_value_error`, `unit/test_link_parameters.py::test_coefficient_domain_endpoints_and_infinity`, `unit/test_link_parameters.py::test_from_link_two_thresholds_and_exact_context`, `unit/test_link_parameters.py::test_from_link_rejects_nonpositive_or_nonfinite_inputs`, `unit/test_link_parameters.py::test_from_link_rejects_overrides_and_names_out_of_domain_coefficient` |
| G47 | An infeasible allocation yields analytic [1,1] before the C-INR or zero-gain shortcuts; required_snr excludes it, except for the sufficient Chernoff rule. The nonpositive SIC margin is checked before division. | `src/certoutage/models.py`, `src/certoutage/api.py` | `unit/test_link_parameters.py::test_infeasible_allocation_precedes_division`, `unit/test_link_parameters.py::test_infeasible_is_analytic_one`, `unit/test_link_parameters.py::test_infeasible_precedes_direct_zero_gain_and_inr_limit` |
| G48 | Bank arguments are scaled outward; the identity preserves the arrays and exact J_max grid products stay unchanged. Exact-Fraction checks include non-dyadic factors, zero and subnormals. The inherited lookup extends monotonically with 0 below and 1 above the bank range. | `src/certoutage/_runtime.py`, `src/certoutage/api.py`, `src/certoutage/_vendor/oracles.py` | `unit/test_link_parameters.py::test_scale_outward_against_exact_fractions`, `unit/test_link_parameters.py::test_largest_grid_retains_only_exact_products`, `unit/test_link_parameters.py::test_signal_lookup_extends_with_zero_and_one`, `unit/test_link_parameters.py::test_largest_interferer_user_equivalence_and_certificate_guard` |
| G49 | g is applied once to the evaluation argument; at g=0 all interference choices have the same raw bounds as none, preserve the requested quantity and have analytic zero floors for finite d. Tested on bank and direct paths; C-TX folding also checks PPP, Gamma and mean. | `src/certoutage/api.py`, `src/certoutage/_runtime.py` | `unit/test_link_parameters.py::test_zero_gain_is_exactly_no_interference`, `unit/test_link_parameters.py::test_tx_gain_folding_overlaps` |
| G50 | Sampled C-INR scaling and C-TX gain folding enclosures overlap; C-TX scaling in d alone is strictly different on an informative case. User 2 equals user 1 with d1=160 bit for bit in bank, direct and J_max computations. Sampled d and g grids have no contradictory monotonicity. | `src/certoutage/api.py`, `src/certoutage/_runtime.py` | `unit/test_link_parameters.py::test_inr_scaling_overlaps_with_nondyadic_ratio`, `unit/test_link_parameters.py::test_tx_gain_folding_overlaps`, `unit/test_link_parameters.py::test_tx_link_scaling_alone_is_not_an_identity`, `unit/test_link_parameters.py::test_user_selects_only_d_in_bank_and_direct_routes`, `unit/test_link_parameters.py::test_largest_interferer_user_equivalence_and_certificate_guard`, `unit/test_link_parameters.py::test_link_and_gain_monotonicity` |
| G51 | threshold_difference rejects different or missing d1, d2 or g and compares equivalent rational spellings without passing fractions to Decimal. | `src/certoutage/api.py` | `unit/test_link_parameters.py::test_threshold_difference_rejects_different_links`, `unit/test_link_parameters.py::test_threshold_difference_compares_rationals_and_missing_keys` |
| G52 | Direct thermal integration accepts per-call d, with an Arb amplitude transported outward. For d=40 and 500, its enclosure overlaps the signal-bank enclosure at N=8,64 (m=1) and N=8 (m=2); warm and cleared thermal caches give identical bounds across different d. | `src/certoutage/api.py`, `src/certoutage/_runtime.py` | `unit/test_link_parameters.py::test_direct_arbitrary_link_overlaps_bank`, `unit/test_link_parameters.py::test_thermal_cache_is_independent_of_link` |
| G53 | Every API contract records canonical d1, d2 and g at the end of parameters and actual link assumptions, including infeasibility. The default assumptions tuple remains character-for-character identical. | `src/certoutage/api.py` | `unit/test_link_parameters.py::test_contract_assumptions_and_parameter_order`, `unit/test_link_parameters.py::test_comparison_rows_record_actual_links_and_limits` |
| G54 | eta is read as an exact decimal in [2.1,8], canonicalized before cache and bank naming; equivalent 3/4 spellings reuse their bank, other eta never reuse embedded arrays. | `src/certoutage/models.py`, `src/certoutage/_runtime.py` | `unit/test_real_eta.py::test_eta_canonicalization`, `unit/test_real_eta.py::test_eta_invalid_fast`, `unit/test_real_eta.py::test_canonical_cache_and_bank_names` |
| G55 | The explicit transform at canonical eta=3,4 retains identical midpoints and radii; generated eta=3 arrays retain every byte when compared with direct explicit dispatch. | `src/certoutage/_transform.py`, `src/certoutage/_generate.py` | `unit/test_real_eta.py::test_explicit_transform_is_identical`, `unit/test_real_eta.py::test_explicit_arrays_are_identical` |
| G56 | General 2F1 integrals overlap the explicit path on every tested M=2^12 frequency and independent Acb integrals at eight exponents; M=2^16 CDF arrays overlap nodewise with the stated width bound. | `src/certoutage/_transform.py`, `src/certoutage/_generate.py` | `unit/test_real_eta.py::test_general_matches_explicit_frequency_grid`, `unit/test_real_eta.py::test_general_arrays_overlap_with_bounded_width`, `unit/test_real_eta.py::test_general_matches_independent_integral` |
| G57 | 2F1 is called on its argument with abc=True; finiteness and relative radius are checked, precision is doubled once, and Pfaff adds a certified geometric remainder or raises. The sampled eta=3.5 grid needs no fallback. | `src/certoutage/_transform.py` | `unit/test_real_eta.py::test_hypergeom_argument_and_abc_flag`, `unit/test_real_eta.py::test_hypergeom_retry_and_fallback`, `unit/test_real_eta.py::test_hypergeom_retry_recovers_without_fallback`, `unit/test_real_eta.py::test_pfaff_truncated_series_contains_reference`, `unit/test_real_eta.py::test_pfaff_rejects_uncertified_ratio`, `unit/test_real_eta.py::test_real_eta_grid_needs_no_fallback` |
| G58 | D_M is computed with certified inequalities and binary64 boundary brackets; the values of PROOFS.md, Proposition 4.6, and sampled monotonicities agree. General PPP contracts announce the domain without rejecting outside points; legacy contract notes stay unchanged. | `src/certoutage/_transform.py`, `src/certoutage/api.py` | `unit/test_real_eta.py::test_remainders_e6_and_monotonicities`, `unit/test_real_eta.py::test_lambda_window_certifies_boundaries_and_empty_case`, `unit/test_real_eta.py::test_ppp_domain_notes_and_legacy_contracts`, `unit/test_real_eta.py::test_technical_domain_corners` |
| G59 | Decimal adjusted exponents are bounded before exact fraction conversion; extreme inputs fail promptly, zero spellings pass where admissible, and rational strings retain exact parsing. | `src/certoutage/models.py` | `unit/test_real_eta.py::test_exponent_bounds_precede_fraction`, `unit/test_real_eta.py::test_eta_invalid_fast` |
| G60 | Acb inverse DFT has the 1/M normalization, independently checked against the direct sum at M=8,16; the generator's M/B factor is preserved. | `src/certoutage/_generate.py` | `unit/test_real_eta.py::test_inverse_dft_normalization` |
| G61 | At eta=3.5 all interference models, both conventions and users return probabilities and canonical parameters; sampled outage, floor and J_max intervals obey disjoint eta ordering. | `src/certoutage/api.py`, `src/certoutage/_runtime.py` | `unit/test_real_eta.py::test_real_eta_all_natures`, `unit/test_real_eta.py::test_eta_monotonicity`, `unit/test_real_eta.py::test_technical_domain_corners` |
| G62 | Threshold differences reject different real exponents and accept equivalent exact decimal spellings. | `src/certoutage/api.py` | `unit/test_real_eta.py::test_threshold_difference_uses_exact_eta` |
| G63 | The statements of `docs/PROOFS.md` (provisional proofs) listed as independently tested in its § 6 are checked against reference values that do not come from the package: the 2F1 identities by Acb quadrature over the whole technical range of eta (2.1 to 8); the Fourier majorant by quadrature (eta from 2.1 to 8, three values of c, t up to 10⁴ in absolute value); the truncation remainder R on a distribution with explicit CDF (bound nearly attained; the half-weight convention is checked separately by the DFT identification at the nodes); the derivatives of log R by finite differences of its closed formula; the integral inequality of the tail τ and the cumulant series by quadrature. The statements of § 1, the sample tests of § 4 and the cumulants against `moment` go through the package (G45–G50, G58); the statements without a test of their own are listed in § 6. Finitely many cases; the tests do not replace the proofs. | `docs/PROOFS.md`, `src/certoutage/_transform.py`, `src/certoutage/_generate.py` | `unit/test_real_eta.py::test_general_matches_independent_integral`, `unit/test_real_eta.py::test_general_matches_independent_integral_near_two`, `unit/test_real_eta.py::test_pfaff_truncated_series_contains_reference`, `unit/test_proofs.py::test_statement_a_majorant`, `unit/test_proofs.py::test_statement_b_on_a_known_distribution`, `unit/test_proofs.py::test_dft_identification_at_the_nodes`, `unit/test_proofs.py::test_domain_derivatives_by_finite_differences`, `unit/test_proofs.py::test_statement_c_and_cumulants` |
| G64 | The transform and D_M notes appear only on results that use a PPP inversion with eta other than 3 or 4 (noninteger, or an integer from 5 to 8, which also takes the 2F1 path); λ=0, g=0, infeasible and analytic results carry neither, the explicit eta=3,4 paths carry neither, and λ=0 or g=0 give the bounds of the case without interference. | `src/certoutage/api.py` | `unit/test_real_eta.py::test_domain_notes_only_when_a_ppp_inversion_contributes`, `unit/test_real_eta.py::test_real_eta_all_natures` |

## Stated, not yet checked by a test

These promises appear in the documentation. They are believed to hold, but
no test checks them yet:

- A target equal to an endpoint is compared exactly with the binary value,
  with no tolerance (API). Covered only indirectly by the regressions.
- The binary search checks its two final points again, and
  `undecided_points` counts the points between the two finite edges (API).
  Checked only by the regressions.
- Results are immutable dataclasses exported by `dataclasses.asdict`;
  `compare_approximations` returns six rows; `gauss` and `GAMMA` are not
  public method names (API).
- The wheel and the sdist both contain every bank (README). Checked on the
  distributions built on 26 November 2026 (all 43 banks and the manifest,
  byte for byte, manifest digest equal to the pinned one), but not yet by an
  automated test of the built distributions.
- No linear interpolation and no renormalization of tails; F_J(0)=0
  (CONTRACT). These are properties of the construction, argued in the
  contract.
- The version DOI quoted in the README is that of the release (the version
  and the date quoted there are checked, G34).
- The diagnostics are checked on the Table II example only (G28), and
  monotonicity on one model (G18).
- `target` is kept on every decision, including exclusions, inconclusive
  searches and the J_max row (API). Exercised by the Table II regression
  and by G27, not by a dedicated test.
- Changing a bank on disk does not retroactively change arrays that are
  already loaded (API).
- Normal use never reads the original archive (README). G05 and G06 cover
  network access and writes, not reads.
