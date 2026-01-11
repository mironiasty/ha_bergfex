from custom_components.bergfex.parser import parse_cross_country_resort_page
from custom_components.bergfex.const import KEYWORDS
from datetime import datetime
import pytest


def test_parse_cross_country_achensee_overview():
    html = """
    <div class="tailwind">
    <h1 class="tw-text-4xl">
    <span class="tw-font-normal">Langlaufen</span>
    <span>Achensee - Tirols Sport & Vital Park</span>
    </h1>
    </div>
    <div class="contentbox box-container">
    <div class="box-header">Loipen Bericht</div>
    <div class="box-content">
    <div class="report-info">
    <div class="report-value"><span class="big">58,5</span> km</div>
    <div class="report-label">Klassisch</div>
    </div>
    <div class="report-info">
    <div class="report-value"><span class="big">82,5</span> km</div>
    <div class="report-label">Skating</div>
    </div>
    </div>
    </div>
    """
    data = parse_cross_country_resort_page(html, lang="at")
    assert data["resort_name"] == "Langlaufen Achensee - Tirols Sport & Vital Park"
    assert data["classical_distance_km"] == 58.5
    assert data["skating_distance_km"] == 82.5
    assert data["status"] == "Open"


def test_parse_cross_country_detailed():
    html = """
    <dl class="dl-horizontal dt-large loipen-bericht">
        <dt>Loipenbericht</dt>
        <dd>Heute, 11:52</dd>
        
        <dt>Betrieb</dt>
        <dd>täglich</dd>
        
        <dt class="big">Loipen klassisch</dt>
        <dd class="big">
            58,5 km
            <span class="default-size">gespurt</span>
            <span class="default-size">(sehr gut)</span>
        </dd>
        
        <dt class="big">Loipen Skating</dt>
        <dd class="big">
            82,5 km 
            <span class="default-size">gespurt</span>
            <span class="default-size">(sehr gut)</span>
        </dd>
    </dl>
    """
    data = parse_cross_country_resort_page(html, lang="at")
    assert data["classical_distance_km"] == 58.5
    assert data["classical_condition"] == "gespurt (sehr gut)"
    assert data["skating_distance_km"] == 82.5
    assert data["skating_condition"] == "gespurt (sehr gut)"
    assert data["operation_status"] == "täglich"
    assert isinstance(data["last_update"], datetime)
    assert data["status"] == "Open"


@pytest.mark.parametrize("lang", list(KEYWORDS.keys()))
def test_parse_cross_country_all_languages(lang):
    """Test parsing cross country data for all supported languages."""
    kw = KEYWORDS[lang]

    # Use fallback if keyword missing (shouldn't happen with our recent update)
    trail_report = kw.get("trail_report", "Loipenbericht")
    operation = kw.get("operation", "Betrieb")
    classical = kw.get("classical", "klassisch")
    # Add some text around to simulate real headers like "Loipen klassisch" vs "klassisch"
    # But for the test, we want to ensure the KEYWORD matches.
    # If the regex in parser is `classical_kw.lower() in dt.text.lower()`,
    # then putting the keyword directly in DT is sufficient.
    classical_header = f"Prefix {classical} Suffix"
    skating = kw.get("skating", "Skating")
    skating_header = f"Prefix {skating} Suffix"
    today = kw.get("today", "heute")

    html = f"""
    <dl class="dl-horizontal dt-large loipen-bericht">
        <dt>{trail_report}</dt>
        <dd>{today}, 09:30</dd>
        
        <dt>{operation}</dt>
        <dd>Open</dd>
        
        <dt class="big">{classical_header}</dt>
        <dd class="big">12.5 km</dd>
        
        <dt class="big">{skating_header}</dt>
        <dd class="big">15,0 km</dd>
    </dl>
    """

    data = parse_cross_country_resort_page(html, lang=lang)

    assert data["classical_distance_km"] == 12.5, f"Failed classical for {lang}"
    assert data["skating_distance_km"] == 15.0, f"Failed skating for {lang}"
    assert isinstance(data.get("last_update"), datetime), f"Failed date for {lang}"
    assert data.get("operation_status"), f"Failed operation for {lang}"
