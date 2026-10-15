"""Guess which channel is foci / brightfield / membrane from metadata."""
from __future__ import annotations

import re

from .io import ChannelInfo, _is_bf

# fluorophores typically used for the foci channel (red/orange emitters)
_FOCI_RE = re.compile(r"rhod|tritc|cy3|cherry|rfp|tomato|texas|\bred\b|(?:af|alexa\s*fluor)\s*(?:546|555|568|594)", re.I)


def guess_roles(chs: list[ChannelInfo]) -> tuple[dict[str, int], str]:
    """Return ({'ch_red': i, 'ch_bf': j, 'ch_green': k} (only roles found), explanation).

    - brightfield: contrast/illumination says brightfield/transmitted/phase/DIC
    - foci: fluorescence channel whose name/dye looks red/orange (Rhodamine, mCherry, Cy3, AF555-594...);
      otherwise the shorter-emission fluorescence channel (or the first one if wavelengths are unknown)
    - membrane (segmentation channel): the first remaining fluorescence channel
    NB: roles follow dye/contrast, not display colour (e.g. AF647 is often shown green).
    """
    if not chs:
        return {}, "no channel metadata"
    roles: dict[str, int] = {}
    bf = [i for i, c in enumerate(chs) if _is_bf(c)]
    fl = [i for i in range(len(chs)) if i not in bf]
    if bf:
        roles["ch_bf"] = bf[0]
    foci = next((i for i in fl if _FOCI_RE.search(f"{chs[i].name} {chs[i].fluor}")), None)
    if foci is None and len(fl) >= 2:
        # no red-looking dye: take the shorter-emission channel as foci when wavelengths are known
        known = [i for i in fl if chs[i].emission]
        foci = min(known, key=lambda i: chs[i].emission) if len(known) == len(fl) else fl[0]
    if foci is not None:
        roles["ch_red"] = foci
    rest = [i for i in fl if i != foci]
    if rest:
        roles["ch_green"] = rest[0]
    why = ", ".join(f"{k.replace('ch_', '')}→{v}:{chs[v].label()}" for k, v in roles.items())
    return roles, why
