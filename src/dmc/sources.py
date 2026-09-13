"""Source configuration is data, independent of processing and publication."""

from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass(frozen=True)
class Source:
    label: str
    title: str
    description: str
    item_id: int
    report_type_id: int
    navigation_language: str = "en"

    def page_url(self, offset: int) -> str:
        return "https://www.dmc.gov.lk/index.php?" + urlencode(
            {
                "option": "com_dmcreports",
                "view": "reports",
                "Itemid": self.item_id,
                "report_type_id": self.report_type_id,
                "lang": self.navigation_language,
                "limitstart": offset,
            }
        )


SOURCES = {
    source.label: source
    for source in (
        Source(
            "lk_dmc_situation_reports",
            "Situation reports",
            "Reports on heavy rain, wind, lightning, and other disaster impacts.",
            273,
            1,
        ),
        Source(
            "lk_dmc_weather_forecasts",
            "Weather forecasts",
            "Weather forecasts for Sri Lanka.",
            274,
            2,
            "si-ta-en",
        ),
        Source(
            "lk_dmc_river_water_level_and_flood_warnings",
            "River and flood warnings",
            "River water levels and flood warnings for Sri Lanka.",
            277,
            6,
        ),
        Source(
            "lk_dmc_landslide_warnings",
            "Landslide warnings",
            "Landslide early warnings and locations at risk.",
            276,
            5,
        ),
    )
}
