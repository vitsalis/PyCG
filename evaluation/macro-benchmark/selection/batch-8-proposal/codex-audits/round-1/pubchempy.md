Pubchempy, round 1: **no findings**.

Read every function body in `pubchempy.py`, including nested functions,
both lambdas, and both `Compound.record` accessors. Checked all **373
graph edges: 233 inside and 140 outside**. The graph and added-edge file
contain identical edge sets. No package execution, imports, downloads,
writes, or analysis-tool output were used.

The inventory counts unique outgoing graph edges. Function names have
the prefix `pubchempy.`. The getter and setter of `Compound.record` share
one graph node; both bodies were checked.

| Function read | Edges checked |
|---|---:|
| `pubchempy` (module, class bodies and decorators) | 12 |
| `request` | 14 |
| `get` | 6 |
| `get_json` | 5 |
| `get_sdf` | 4 |
| `get_compounds` | 3 |
| `get_substances` | 3 |
| `get_assays` | 2 |
| `get_properties` | 6 |
| `get_synonyms` | 1 |
| `get_cids` | 1 |
| `get_sids` | 1 |
| `get_aids` | 1 |
| `get_all_sources` | 3 |
| `download` | 5 |
| `memoized_property` | 3 |
| `memoized_property.fget_memoized` | 9 |
| `deprecated` | 0 |
| `deprecated.deco` | 2 |
| `deprecated.deco.wrapped` | 10 |
| `Atom.__init__` | 0 |
| `Atom.__repr__` | 1 |
| `Atom.__eq__` | 3 |
| `Atom.__getitem__` | 3 |
| `Atom.__setitem__` | 1 |
| `Atom.__contains__` | 2 |
| `Atom.element` | 2 |
| `Atom.to_dict` | 2 |
| `Atom.set_coordinates` | 0 |
| `Atom.coordinate_type` | 0 |
| `Bond.__init__` | 0 |
| `Bond.__repr__` | 0 |
| `Bond.__eq__` | 2 |
| `Bond.__getitem__` | 2 |
| `Bond.__setitem__` | 1 |
| `Bond.__contains__` | 1 |
| `Bond.__delitem__` | 3 |
| `Bond.to_dict` | 0 |
| `Compound.__init__` | 1 |
| `Compound._setup_atoms` | 8 |
| `Compound._setup_bonds` | 6 |
| `Compound.from_cid` | 6 |
| `Compound.record` (getter and setter) | 4 |
| `Compound.__repr__` | 1 |
| `Compound.__eq__` | 3 |
| `Compound.to_dict` | 50 |
| `Compound.to_series` | 2 |
| `Compound.cid` | 1 |
| `Compound.elements` | 2 |
| `Compound.atoms` | 3 |
| `Compound.atoms.<lambda1>` | 0 |
| `Compound.bonds` | 3 |
| `Compound.bonds.<lambda1>` | 0 |
| `Compound.synonyms` | 2 |
| `Compound.sids` | 2 |
| `Compound.aids` | 2 |
| `Compound.coordinate_type` | 1 |
| `Compound.charge` | 1 |
| `Compound.molecular_formula` | 2 |
| `Compound.molecular_weight` | 3 |
| `Compound.canonical_smiles` | 1 |
| `Compound.isomeric_smiles` | 1 |
| `Compound.connectivity_smiles` | 2 |
| `Compound.smiles` | 2 |
| `Compound.inchi` | 2 |
| `Compound.inchikey` | 2 |
| `Compound.iupac_name` | 2 |
| `Compound.xlogp` | 2 |
| `Compound.exact_mass` | 3 |
| `Compound.monoisotopic_mass` | 3 |
| `Compound.tpsa` | 2 |
| `Compound.complexity` | 2 |
| `Compound.h_bond_donor_count` | 2 |
| `Compound.h_bond_acceptor_count` | 2 |
| `Compound.rotatable_bond_count` | 2 |
| `Compound.fingerprint` | 2 |
| `Compound.cactvs_fingerprint` | 3 |
| `Compound.heavy_atom_count` | 1 |
| `Compound.isotope_atom_count` | 1 |
| `Compound.atom_stereo_count` | 1 |
| `Compound.defined_atom_stereo_count` | 1 |
| `Compound.undefined_atom_stereo_count` | 1 |
| `Compound.bond_stereo_count` | 1 |
| `Compound.defined_bond_stereo_count` | 1 |
| `Compound.undefined_bond_stereo_count` | 1 |
| `Compound.covalent_unit_count` | 1 |
| `Compound.volume_3d` | 2 |
| `Compound.multipoles_3d` | 2 |
| `Compound.conformer_rmsd_3d` | 2 |
| `Compound.effective_rotor_count_3d` | 2 |
| `Compound.pharmacophore_features_3d` | 2 |
| `Compound.mmff94_partial_charges_3d` | 2 |
| `Compound.mmff94_energy_3d` | 2 |
| `Compound.conformer_id_3d` | 2 |
| `Compound.shape_selfoverlap_3d` | 2 |
| `Compound.feature_selfoverlap_3d` | 2 |
| `Compound.shape_fingerprint_3d` | 2 |
| `_parse_prop` | 5 |
| `Substance.__init__` | 0 |
| `Substance.from_sid` | 6 |
| `Substance.record` | 0 |
| `Substance.__repr__` | 1 |
| `Substance.__eq__` | 3 |
| `Substance.to_dict` | 9 |
| `Substance.to_series` | 2 |
| `Substance.sid` | 1 |
| `Substance.synonyms` | 1 |
| `Substance.source_name` | 1 |
| `Substance.source_id` | 1 |
| `Substance.standardized_cid` | 2 |
| `Substance.standardized_compound` | 2 |
| `Substance.deposited_compound` | 3 |
| `Substance.cids` | 2 |
| `Substance.aids` | 2 |
| `Assay.__init__` | 0 |
| `Assay.from_aid` | 6 |
| `Assay.record` | 0 |
| `Assay.__repr__` | 1 |
| `Assay.__eq__` | 3 |
| `Assay.to_dict` | 12 |
| `Assay.aid` | 1 |
| `Assay.name` | 1 |
| `Assay.description` | 1 |
| `Assay.project_category` | 3 |
| `Assay.comments` | 1 |
| `Assay.results` | 1 |
| `Assay.target` | 1 |
| `Assay.revision` | 1 |
| `Assay.aid_version` | 1 |
| `compounds_to_frame` | 4 |
| `substances_to_frame` | 4 |
| `PubChemHTTPError.__init__` | 2 |
| `PubChemHTTPError.__str__` | 1 |
| `PubChemHTTPError.__repr__` | 0 |
| `create_http_error` | 5 |
| **Total: 134 function nodes and one module** | **373** |

No missing, false, naming, ruling, or unsure finding remained after
checking value sites, default rejections, implicit calls, binding,
wrapper dispatch, library callbacks, and outside names. The existing
batch-8 rulings for J2, J5 and J6 were applied. There are no declared
open path sets or applicable open receiver sets.

| Id | Kind | Caller | Site (file:line:col) | Edge | Evidence | Rule |
|---|---|---|---|---|---|---|

| Missing | False | Naming | Ruling | Unsure |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |