import unittest

from chartist.views.macro_view import METRIC_BY_KEY, loadCountries


class MacroMapTests(unittest.TestCase):
    def test_loads_country_boundaries_and_metrics(self):
        countries = loadCountries()

        self.assertGreater(len(countries), 170)
        united_states = next(
            country for country in countries if country.iso == "USA"
        )
        self.assertEqual(united_states.continent, "North America")
        self.assertIn("growth", united_states.values)
        self.assertGreater(united_states.population, 300_000_000)

    def test_generated_metrics_remain_in_display_ranges(self):
        for country in loadCountries():
            for key, metric in METRIC_BY_KEY.items():
                value = country.values[key]
                if key != "gdp_pc":
                    self.assertGreaterEqual(value, metric.low)
                    self.assertLessEqual(value, metric.high)


if __name__ == "__main__":
    unittest.main()
