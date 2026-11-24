"""Figure 1 entière, Table I et campagne Nakagami, valeurs brutes."""
import csv
from pathlib import Path

from certoutage import Model, outage_enclosure, required_snr, threshold_difference

FIXTURES = Path(__file__).parent / "fixtures"


def test_figure_1_eight_sizes():
    for row in csv.DictReader((FIXTURES / "FIGURE_1.csv").open()):
        model = Model(N=int(row["N"]), convention="C-INR")
        ppp = required_snr(model, 1, "1e-5")
        mean = required_snr(model, 1, "1e-5", interference="mean")
        eq3 = required_snr(model, 1, "1e-5", gain="eq3", interference="mean")
        for label, left, right in [("interference", mean, ppp), ("gain", eq3, mean), ("total", eq3, ppp)]:
            actual = threshold_difference(left, right)
            assert actual.lower == float(row[label + "_error_lower"])
            assert actual.upper == float(row[label + "_error_upper"])


def test_table_i_all_endpoints():
    for row in csv.DictReader((FIXTURES / "TABLE_I_CERTIFICATS.csv").open()):
        model = Model(N=int(row["N"]), m=int(row["m"]), lam=0)
        method = "eq3" if row["method"] == "gauss" else row["method"]
        for prefix in ["previous", "chosen"]:
            actual = outage_enclosure(model, 1, row[prefix + "_db"], gain=method)
            assert actual.as_dict() == {side: float(row[prefix + "_" + side]) for side in ["lower", "upper"]}
    censored = outage_enclosure(Model(N=8, lam=0), 1, 40, gain="eq3")
    assert censored.lower > 1e-5


def test_nakagami_twenty_cases():
    for row in csv.DictReader((FIXTURES / "nakagami.csv").open()):
        model = Model(N=int(row["N"]), m=int(row["m"]), convention=row["convention"])
        for key, gain, kind in [("exact_PPP", "exact", "PPP"), ("exact_mean", "exact", "mean"), ("gauss_mean", "eq3", "mean")]:
            if not row[key + "_status"]:
                continue
            result = required_snr(model, 1, "1e-5", gain=gain, interference=kind)
            for side in ["lower", "upper"]:
                v = row[key + "_" + side + "_db"]
                assert getattr(result, side + "_db") == (float(v) if v else None)
                assert getattr(result.floor, side) == float(row[key + "_floor_" + side])
