from fociquant.channels import guess_roles
from fociquant.io import ChannelInfo, parse_zeiss_info

INFO = """
 Information|Image|Channel|ContrastMethod #1 = Fluorescence
 Information|Image|Channel|ContrastMethod #2 = Brightfield
 Information|Image|Channel|ContrastMethod #3 = Fluorescence
 Information|Image|Channel|EmissionWavelength #1 = 575
 Information|Image|Channel|EmissionWavelength #2 = 668
 Information|Image|Channel|Fluor #1 = Rhodamine
 Information|Image|Channel|Fluor #2 = TL Brightfield
 Information|Image|Channel|Fluor #3 = Alexa Fluor 647
 Information|Image|Channel|IlluminationType #1 = Epifluorescence
 Information|Image|Channel|IlluminationType #2 = Transmitted
 Information|Image|Channel|IlluminationType #3 = Epifluorescence
 Information|Image|Channel|Name #1 = Rhoda
 Information|Image|Channel|Name #2 = Bright
 Information|Image|Channel|Name #3 = AF647
"""


def test_parse_zeiss_info():
    chs = parse_zeiss_info(INFO, 3)
    assert [c.name for c in chs] == ["Rhoda", "Bright", "AF647"]
    assert [c.emission for c in chs] == [575.0, None, 668.0]     # emissions skip the brightfield channel
    assert parse_zeiss_info(INFO, 4) == []                        # count mismatch -> no metadata


def test_roles_follow_dye_not_display_colour():
    roles, _ = guess_roles(parse_zeiss_info(INFO, 3))
    assert roles == {"ch_bf": 1, "ch_red": 0, "ch_green": 2}


def test_roles_other_order_and_dyes():
    chs = [ChannelInfo("DIC", "", "Brightfield", "Transmitted"),
           ChannelInfo("GFP", "GFP", "Fluorescence", "Epifluorescence", 509),
           ChannelInfo("mCh", "mCherry", "Fluorescence", "Epifluorescence", 610)]
    roles, _ = guess_roles(chs)
    assert roles == {"ch_bf": 0, "ch_red": 2, "ch_green": 1}


def test_no_metadata():
    assert guess_roles([])[0] == {}
