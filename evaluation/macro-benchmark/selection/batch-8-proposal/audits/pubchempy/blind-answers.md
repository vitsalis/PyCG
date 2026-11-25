# pubchempy: blind answers (146 sites, seed 20261124)

Written from the source (`pubchempy.py` at `9935a14`), `pyproject.toml`,
`docs/`, `tests/`, the CPython sources of the dependency set and the README's
rules only, before I opened any file of the writer. The skeleton was made in
a scratch copy without a ledger (`check.py --benchmark-dir <scratch>
--skeleton pubchempy`): 901 sites (243 call, 86 decorator, 32 iter, 19
mapping, 89 op, 264 getitem, 5 setitem, 134 getattr, 1 setattr, 28 format),
8 value sites.

## The draw

`draw.py` numbers the skeleton's sites by (module, line, column) (one
module) and draws with one `random.Random(20261124)`:
`rng.sample(explicit, 90)`, then `rng.sample(implicit, 50)`. The split: 572
of the 901 sites are implicit, and 372 of these are subscripts, comparisons
and `**` of JSON dicts and builtin values whose only candidates are the
`__getitem__`, `__eq__` and `__contains__` of the five record classes; the
329 explicit sites carry the outside callees and the package dispatch. A
plain draw of 140 would give about 51 explicit sites. The 8 value sites are
added; 2 were drawn (803:6, 1742:19), so 6 are added. 146 sites in
`sample.txt`.

## Conventions I apply (decided before the comparison)

| Id | Case | Decision | Rule |
|---|---|---|---|
| K1 | `.read()` of the response of `request()` (`urlopen` of an https URL) | `http.client.HTTPResponse.read`, and `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper` for the `addinfourl` of a server redirect to ftp (urllib's `HTTPRedirectHandler` admits http, https, ftp, `Lib/urllib/request.py:707` in 3.10) | "A branch that a server's answer decides runs" (asciinema); naming of fastjsonschema `ref_resolver.py:73` and asciinema J9 |
| K2 | `e.read()` of an `HTTPError` | `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper` only (`HTTPError` inherits `addinfourl`, which defines no `read`) | as K1 |
| K3 | `log.info(e)` with `e` a `NotFoundError` (`get_json`, `get_sdf`) | `logging.Logger.info` and `pubchempy.PubChemHTTPError.__str__`: the documented setup (`docs/guide/advanced.md:30-46`, `logging.basicConfig(level=logging.DEBUG)`) formats the record, and `LogRecord.getMessage` calls `str(self.msg)` | B5 (pyrate-limiter `limiter.py:182`, structlog) |
| K4 | the methods that `@deprecated(...)` wraps (Atom and Bond `__getitem__`, `__setitem__`, `__contains__`, Bond `__delitem__`, `Compound.canonical_smiles`, `isomeric_smiles`) | the class attribute is `pubchempy.deprecated.deco.wrapped`; a subscript or attribute load reaches `wrapped`, and `wrapped` calls the method at `823:24`. The package itself never subscripts an `Atom` or a `Bond` | "A method that a decorator ... wraps": the wrapper is the callee |
| K5 | `@memoized_property` (Compound `synonyms`, `sids`, `aids`; Substance `standardized_compound`, `cids`, `aids`) | the property's fget is `pubchempy.memoized_property.fget_memoized`, which calls the method at `806:42` | as K4 |
| K6 | `getattr(self, p)` in the three `to_dict` | `<builtin>.getattr` and, as call-backs, the fget of every property whose name reaches `p`: the package's default list (every `property` of the class `__dict__` but the skip set), `"cid"`/`"sid"` of the frame functions, and the names that the documentation gives: `atoms`, `bonds`, `inchi` (`docs/guide/compound.md:19`), `smiles`, `xlogp`, `rotatable_bond_count` (`docs/guide/pandas.md:29`), and the docstrings' "not included unless explicitly specified" (`synonyms`, `aids`, `sids` of Compound; `cids`, `aids` of Substance) and "not included by default" (`canonical_smiles`, `isomeric_smiles`) | B3 (an attribute name of the client names a property only where documented), B2 (documentation names the value for the role); uncertainties ruling (a builtin that invokes a package special method on an admitted argument) |
| K7 | the values of a JSON record (`self.record[...]`, `props[0]["value"]`, `fault`) | `dict` (the package's records come from `json.loads` of PubChem's JSON); a client record is opaque below its top-level `dict` | B2 (package flow), B4 (`record: dict[str, t.Any]`) |
| K8 | `Bond.__delitem__` (`984-988`) | no edge: `self.__wrapped` is `self._Bond__wrapped`, which no `Bond` has, so the argument of `hasattr` raises `AttributeError` before the call, and nothing after it runs | "Edges": a call that cannot happen; B2 (no client assignment of a private attribute) |
| K9 | `ProjectCategory(...)` (`1980`) | `enum.EnumMeta.__call__` (3.10) and `enum.EnumType.__call__` (3.11 to 3.15); no `__init__` | einops metaclass ruling; "retain an older fallback name"; versions `>=3.10` |
| K10 | pandas and certifi | missing modules (not in the dependency set; extras): `pandas.DataFrame.from_records`, `pandas.Series`, `certifi.where` | "Missing modules" |
| K11 | a package exception class call | the first `__init__` of its MRO: `PubChemHTTPError.__init__` for the HTTP errors, `<builtin>.Exception.__init__` for `ResponseParseError` | micro-benchmark "Instantiation" |

Supported: CPython 3.10 to 3.15 (`requires-python = ">=3.10"`), OS
Independent; no PyPy. `from __future__ import annotations`: annotations are
no sites.

## Explicit sites (90)

| Site | Node | Callees | Candidates rejected |
|---|---|---|---|
| 24:21 `os.getenv(...)` | `pubchempy` | `os.getenv` | |
| 24:57 `os.getenv(...)` | `pubchempy` | `os.getenv` | |
| 351:25 `str(identifier)` | `request` | `<builtin>.str` | the seven `__repr__`/`__str__`: `identifier` is an `int` here (`isinstance` at 350) |
| 359:40 `identifier.replace` | `request` | `<builtin>.str.replace` | |
| 366:40 `identifier.encode` | `request` | `<builtin>.str.encode` | |
| 368:29 `urlencode([...])` | `request` | `urllib.parse.urlencode` | |
| 378:18 `log.debug(f"...")` | `request` | `logging.Logger.debug` | |
| 380:27 `urlopen(...)` | `request` | `urllib.request.urlopen` | |
| 400:44 `response.decode()` | `get` | `<builtin>.bytes.decode` | |
| 419:23 `request(...).read()` | `get` | K1: `http.client.HTTPResponse.read`, `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper` | |
| 421:27 `request(...)` | `get` | `pubchempy.request` | |
| 423:15 `request(...).read()` | `get` | K1 (both) | |
| 440:26 `json.loads(...)` | `get_json` | `json.loads` | |
| 446:17 `log.info(e)` | `get_json` | `logging.Logger.info`, `pubchempy.PubChemHTTPError.__str__` (K3) | |
| 616:38 `properties.split(",")` | `get_properties` | `<builtin>.str.split` | |
| 757:23 `get_json(...)` | `get_aids` | `pubchempy.get_json` | |
| 791:14 `open(path, "wb")` | `download` | `<builtin>.open` | |
| 792:16 `f.write(response)` | `download` | `io.BufferedWriter.write` | |
| 803:6 `@functools.wraps(fget)` (value site) | `memoized_property` | `functools.partial.__call__` | note: `wraps` returns a `partial` of `update_wrapper` |
| 807:23 `getattr(self, attr_name)` | `memoized_property.fget_memoized` | `<builtin>.getattr` | (no property is named `_synonyms` etc.) |
| 870:23 `isinstance(other, type(self))` | `Atom.__eq__` | `<builtin>.isinstance` | |
| 879:6 `@deprecated(...)` | `pubchempy` | `pubchempy.deprecated.deco` | |
| 884:23 `KeyError(prop)` | `Atom.__getitem__` | `<builtin>.KeyError` | |
| 891:6 `@deprecated(...)` | `pubchempy` | `pubchempy.deprecated.deco` | |
| 891:16 `deprecated(...)` | `pubchempy` | `pubchempy.deprecated` | |
| 907:23 `getattr(self, coord)` | `Atom.to_dict` | `<builtin>.getattr` | (`x`, `y`, `z` are instance attributes) |
| 957:35 `type(self)` | `Bond.__eq__` | `<builtin>.type` | |
| 971:6 `@deprecated(...)` | `pubchempy` | `pubchempy.deprecated.deco` | |
| 987:27 `KeyError(prop)` | `Bond.__delitem__` | none (K8) | note |
| 1050:41 `len(xs)` | `Compound._setup_atoms` | `<builtin>.len` | |
| 1050:52 `len(ys)` | `Compound._setup_atoms` | `<builtin>.len` | |
| 1051:31 `len(zs)` | `Compound._setup_atoms` | `<builtin>.len` | |
| 1053:41 `ResponseParseError(...)` | `Compound._setup_atoms` | `<builtin>.Exception.__init__` (K11) | |
| 1055:49 `self._atoms[aid].set_coordinates(...)` | `Compound._setup_atoms` | `pubchempy.Atom.set_coordinates` | |
| 1070:47 `len(orders)` | `Compound._setup_bonds` | `<builtin>.len` | |
| 1072:37 `zip(aid1s, aid2s, orders)` | `Compound._setup_bonds` | `<builtin>.zip` | `Atom.__getitem__`, `Bond.__getitem__`: the arguments are JSON lists |
| 1087:6 `@classmethod` | `pubchempy` | `<builtin>.classmethod` | |
| 1098:56 `request(cid, **kwargs).read()` | `Compound.from_cid` | K1 (both) | |
| 1098:65 `....decode()` | `Compound.from_cid` | `<builtin>.bytes.decode` | |
| 1106:6 `@record.setter` | `pubchempy` | `<builtin>.property.setter` | |
| 1117:38 `type(self)` | `Compound.__eq__` | `<builtin>.type` | |
| 1183:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1207:22 `sorted(..., key=lambda x: x.aid)` | `Compound.atoms` | `<builtin>.sorted`, `pubchempy.Compound.atoms.<lambda1>` | `Atom.__getitem__`, `Bond.__getitem__`: a `dict_values` view is iterated |
| 1221:31 `get_json(self.cid, operation="synonyms")` | `Compound.synonyms` | `pubchempy.get_json` | `Compound.cid`: loaded at its own attribute site; an int is passed |
| 1274:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1297:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1298:16 `deprecated("Use smiles instead")` | `pubchempy` | `pubchempy.deprecated` | |
| 1334:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1373:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1394:21 `float(sval)` | `Compound.exact_mass` | `<builtin>.float` | |
| 1404:27 `_parse_prop(...)` | `Compound.monoisotopic_mass` | `pubchempy._parse_prop` | |
| 1407:21 `float(sval)` | `Compound.monoisotopic_mass` | `<builtin>.float` | |
| 1431:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1441:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1460:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1480:27 `_parse_prop(...)` | `Compound.fingerprint` | `pubchempy._parse_prop` | |
| 1505:22 `int(self.fingerprint[8:], 16)` | `Compound.cactvs_fingerprint` | `<builtin>.int` | |
| 1507:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1529:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1579:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1585:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1613:31 `_parse_prop(...)` | `Compound.conformer_rmsd_3d` | `pubchempy._parse_prop` | |
| 1624:27 `_parse_prop(...)` | `Compound.effective_rotor_count_3d` | `pubchempy._parse_prop` | |
| 1628:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1654:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1660:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1666:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1670:31 `_parse_prop(...)` | `Compound.feature_selfoverlap_3d` | `pubchempy._parse_prop` | |
| 1674:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1678:31 `_parse_prop(...)` | `Compound.shape_fingerprint_3d` | `pubchempy._parse_prop` | |
| 1687:61 `props[0]["value"].keys()` | `_parse_prop` | `<builtin>.dict.keys` (K7) | |
| 1729:6 `@classmethod` | `pubchempy` | `<builtin>.classmethod` | |
| 1741:28 `json.loads(response)` | `Substance.from_sid` | `json.loads` | |
| 1742:19 `cls(record)` (value site) | `Substance.from_sid` | `pubchempy.Substance.__init__` | note: `cls` is `Substance` (no package subclass; a client subclass inherits the same `__init__`) |
| 1781:53 `Substance.__dict__.items()` | `Substance.to_dict` | `types.MappingProxyType.items` | |
| 1784:27 `getattr(self, p)` | `Substance.to_dict` | `<builtin>.getattr`, `Substance.sid`, `Substance.synonyms`, `Substance.source_name`, `Substance.source_id`, `Substance.standardized_cid`, `memoized_property.fget_memoized` (K6: `cids`, `aids` by the docstring) | (`record`, `deposited_compound`, `standardized_compound`: skipped and named by no document or test) |
| 1801:38 `self.to_dict(properties)` | `Substance.to_series` | `pubchempy.Substance.to_dict` | Assay, Atom, Bond, Compound `to_dict`: the receiver is a Substance |
| 1824:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 1843:37 `Compound.from_cid(cid)` | `Substance.standardized_compound` | `pubchempy.Compound.from_cid` | |
| 1872:27 `get_json(self.sid, ...)` | `Substance.aids` | `pubchempy.get_json` | `Substance.sid`: loaded at its own site |
| 1910:6 `@classmethod` | `pubchempy` | `<builtin>.classmethod` | |
| 1921:87 `....read().decode()` | `Assay.from_aid` | `<builtin>.bytes.decode` | |
| 1953:30 `isinstance(v, property)` | `Assay.to_dict` | `<builtin>.isinstance` | |
| 1962:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 2000:6 `@property` | `pubchempy` | `<builtin>.property` | |
| 2021:18 `isinstance(compounds, Compound)` | `compounds_to_frame` | `<builtin>.isinstance` | |
| 2042:37 `pd.DataFrame.from_records(...)` | `substances_to_frame` | `pandas.DataFrame.from_records` (K10) | |
| 2043:19 `s.to_dict(properties)` | `substances_to_frame` | `pubchempy.Substance.to_dict` | the other four `to_dict`: annotation `list[Substance] \| Substance` |
| 2094:27 `json.loads(e.read().decode())` | `create_http_error` | `json.loads` | |
| 2111:32 `error_map.get(code, PubChemHTTPError)` | `create_http_error` | `<builtin>.dict.get` | `pubchempy.get`: the receiver is a dict |

## Implicit sites (50)

No implicit site of the draw has a package callee but one (1305:21) and the
`record` loads (the receiver's own class). Every candidate of the others is
rejected for the reason given.

| Site | Node | Callees | Reason for the rejections |
|---|---|---|---|
| 362:23 `searchtype == "xref"`, 363:38 `namespace == "cid"`, 364:19 `domain == "sources"` | `request` | none | `str` or `None` operands; the five `__eq__` |
| 402:43 `status["Waiting"]["ListKey"]` | `get` | none | `status` is the dict of `json.loads` |
| 404:53 `"ListKey" in status["Waiting"]` | `get` | none | dict; `Atom`/`Bond.__contains__` and `__eq__` |
| 542:73 `**kwargs` | `get_assays` | none | the dict of `**kwargs` |
| 763:41 `results["IdentifierList"]["AID"]` | `get_aids` | none | JSON dict |
| 866:29 `self.aid` | `Atom.__repr__` | none | `Assay.aid`: the receiver is an Atom, `aid` an instance attribute |
| 876:38 `other.charge` | `Atom.__eq__` | none | `Compound.charge`: `other` is an instance of `type(self)`, an Atom |
| 1049:42, 1049:56 | `Compound._setup_atoms` | none | JSON dict and list |
| 1051:36 `len(zs) == len(coord_ids)` | `Compound._setup_atoms` | none | ints |
| 1083:33, 1083:60 | `Compound._setup_bonds` | none | JSON values |
| 1098:68 `json.loads(...)["PC_Compounds"]` | `Compound.from_cid` | none | JSON dict |
| 1114:27 `{self.cid if self.cid else ''}` | `Compound.__repr__` | none | an int or `''`; the seven `__repr__`/`__str__` |
| 1155:38 `for i in getattr(self, p)` | `Compound.to_dict` | none | the list of `Compound.atoms` or `.bonds` |
| 1158:22 `for p in properties` | `Compound.to_dict` | none | a list or set of strings |
| 1195:31 `self.record["id"]` | `Compound.cid` | none | dict |
| 1237:58, 1249:24 | `Compound.sids`, `Compound.aids` | none | JSON dict |
| 1305:21 `self.smiles` | `Compound.isomeric_smiles` | `pubchempy.Compound.smiles` | |
| 1382:53, 1393:69, 1429:69, 1449:70, 1577:25, 1582:28, 1637:66, 1662:21 `self.record` | the Compound properties | `pubchempy.Compound.record` | `Assay.record`, `Substance.record`: the receiver is a Compound |
| 1548:31, 1564:67, 1582:69 `self.record["count"]`, 1593:27, 1648:27 `self.record["coords"]`, 1643:71 `self.record["props"]`, 1662:40 | Compound properties | none | dict |
| 1558:20 `"count" in self.record` | `Compound.undefined_atom_stereo_count` | none | dict |
| 1741:55 | `Substance.from_sid` | none | JSON |
| 1753:62 `self.record == other.record` | `Substance.__eq__` | none | two dicts of JSON values |
| 1817:27, 1832:25, 1832:37, 1854:23 | Substance properties | none | dict |
| 1955:46 `for p in properties` | `Assay.to_dict` | none | strings |
| 1960:45, 1979:54 | `Assay.aid`, `Assay.project_category` | none | dict |
| 2079:24 `{output}` | `PubChemHTTPError.__str__` | none | a str |
| 2094:46 `json.loads(...)["Fault"]` | `create_http_error` | none | JSON |
| 2096:22 `"Message" in fault` | `create_http_error` | none | dict |

## Value sites not drawn (6)

| Site | Node | Callees | Note |
|---|---|---|---|
| 806:42 `fget(self)` | `memoized_property.fget_memoized` | `Compound.synonyms`, `Compound.sids`, `Compound.aids`, `Substance.standardized_compound`, `Substance.cids`, `Substance.aids` | the six functions that `@memoized_property` decorates; a client's function is opaque |
| 816:10 `@functools.wraps(func)` | `deprecated.deco` | `functools.partial.__call__` | |
| 823:24 `func(*args, **kwargs)` | `deprecated.deco.wrapped` | `Atom.__getitem__`, `Atom.__setitem__`, `Atom.__contains__`, `Bond.__getitem__`, `Bond.__setitem__`, `Bond.__contains__`, `Bond.__delitem__`, `Compound.canonical_smiles`, `Compound.isomeric_smiles` | the nine functions that `@deprecated(...)` decorates (K4) |
| 1099:19 `cls(record)` | `Compound.from_cid` | `pubchempy.Compound.__init__` | |
| 1923:19 `cls(record)` | `Assay.from_aid` | `pubchempy.Assay.__init__` | |
| 2112:23 `error_class(code, msg, details)` | `create_http_error` | `pubchempy.PubChemHTTPError.__init__` | the eight classes of `error_map` and the default define no `__init__` of their own |

## What I expect elsewhere (for Step 2, not part of the count)

- `Compound.to_dict` `getattr(self, p)` at 1155 (`Compound.atoms`,
  `Compound.bonds`) and 1157 (every other Compound property; K6 adds
  `memoized_property.fget_memoized` and `deprecated.deco.wrapped`).
- `Assay.to_dict` at 1955: the nine Assay properties but `record`.
- `get_sdf` `log.info(e)` (467): `PubChemHTTPError.__str__`, as 446.
- `Compound.record` setter: `{self}` at 1109 calls `Compound.__repr__`.
- `Assay.project_category` 1980: K9.
- The `.read()` of `from_sid` (1740) and `from_aid` (1921:78): K1.
- `create_http_error` `e.read()` (2094:36): K2.
- `Atom.__getitem__` and `__contains__` `getattr(self, prop)` (883, 895):
  `Atom.element` as a call-back (`prop` may be `"element"`).
