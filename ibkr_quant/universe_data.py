"""
Seed universe: S&P 500 + curated liquid Nasdaq names.
Used as the starting pool before IBKR ADV ranking.
"""
from __future__ import annotations

from pathlib import Path

SEED_UNIVERSE: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK.B", "LLY", "AVGO",
    "JPM", "UNH", "XOM", "MA", "V", "PG", "COST", "HD", "CVX", "MRK",
    "ABBV", "PEP", "KO", "COP", "WMT", "TMO", "MCD", "CSCO", "ACN", "ABT",
    "CRM", "ADBE", "ABT", "DHR", "LLY", "NEE", "TXN", "PM", "NKE", "ORCL",
    "BMY", "UNP", "INTU", "AMGN", "HON", "QCOM", "LOW", "AMAT", "SPGI", "IBM",
    "CAT", "DE", "ELV", "GILD", "BKNG", "ISRG", "ADI", "SBUX", "MMM", "AXP",
    "LRCX", "MMC", "TJX", "MDT", "VRTX", "NOW", "PFE", "ZTS", "BLK", "SYK",
    "SCHW", "CI", "CI", "CB", "SO", "DUK", "CCI", "AMT", "PLD", "SBAC",
    "EQIX", "PSA", "O", "MSCI", "USB", "SPGI", "CME", "ICE", "AON", "MCO",
    "PGR", "RE", "TGT", "ETN", "EMR", "CARR", "GD", "PH", "CTAS", "WM",
    "CSX", "NSC", "FDX", "RTX", "UPS", "BAE", "LMT", "NOC", "LHX", "HON",
    "GE", "ITW", "SWK", "FTNT", "JCI", "RSG", "PHM", "DHI", "LEN", "NVR",
    "PPG", "APD", "ECL", "SHW", "DD", "FCX", "NUE", "STLD", "DOW", "CE",
    "LYB", "ALB", "CTVA", "FMC", "CF", "MOS", "NTR", "SCCO", "VMC", "MLM",
    "FAST", "MSM", "CPRT", "PCAR", "ODFL", "CHRW", "JBL", "CARR", "TT",
    "ODFL", "EXPD", "GWW", "DOV", "XYL", "ROK", "FTV", "AME", "DCI", "IEX",
    "TDG", "HEI", "TEL", "ANET", "CDW", "EPAM", "MPWR", "KEYS", "TER",
    "ANSS", "SNPS", "CDNS", "CAD", "FORM", "FDS", "GEN", "GLW", "COF",
    "DFS", "BAC", "GS", "MS", "C", "BLK", "AMP", "TFC", "CFG", "STT",
    "SYF", "AFL", "MET", "PRU", "AIG", "TRV", "WRB", "HIG", "CINF",
    "FIS", "FISV", "GPN", "MA", "V", "PYPL", "SQ", "AX", "WFC",
    "PNC", "TFC", "COF", "USB", "MTB", "KEY", "HBAN", "RF", "CMA",
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AMP",
    "COF", "DFS", "SYF", "MTB", "KEY", "HBAN", "RF", "CMA",
    "PYPL", "SQ", "AX", "FIS", "FISV", "GPN",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "ORCL",
    "CSCO", "ADBE", "CRM", "ACN", "TXN", "QCOM", "IBM", "NOW", "INTU", "AMD",
    "INTC", "HON", "PM", "NKE", "CAT", "DE", "ABT", "DHR", "TMO", "UNH",
    "JNJ", "LLY", "PFE", "ABBV", "MRK", "BMY", "AMGN", "GILD", "VRTX",
    "JPM", "UNH", "XOM", "CVX", "WMT", "PG", "KO", "PEP", "MCD",
    "HD", "DIS", "CMCSA", "NFLX", "ADBE", "PYPL", "CRM", "SHOP", "SQ",
    "ZM", "DOCU", "SNOW", "DDOG", "CRWD", "OKTA", "NET", "HUBS", "TEAM",
    "SPLK", "ZS", "FTNT", "PANW", "CHKP", "FTV", "KEYS", "ANET", "CDW",
    "EPAM", "MPWR", "GEN", "CDNS", "SNPS", "ANSS", "CAD", "FDS",
    "LRCX", "AMAT", "ASML", "KLAC", "LRCX", "AMAT", "KLAC", "TER", "MPWR",
    "ON", "MRVL", "QCOM", "AVGO", "MU", "TSM",
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "INTC",
    "QCOM", "AVGO", "ORCL", "IBM", "CSCO", "ACN", "NOW", "INTU", "CRM",
    "ADBE", "PYPL", "SQ", "SHOP", "SNOW", "DDOG", "CRWD", "NET", "OKTA",
    "ZS", "HUBS", "TEAM", "DOCU", "ZM", "SNOW", "FIS", "FISV", "GPN",
    "V", "MA", "PYPL", "COF", "DFS", "AXP", "SYF", "MET", "PRU", "AIG",
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "AMP", "SCHW",
    "USB", "PNC", "TFC", "COF", "CFG", "STT", "RF", "HBAN", "KEY",
    "CME", "ICE", "CBOE", "SPGI", "MCO", "AON", "TRV", "AFL", "MET",
    "BRO", "WRB", "CINF", "HIG", "RE", "PGR", "CB", "TRV",
    "AMT", "PLD", "CCI", "PSA", "EQIX", "O", "SPG", "SBAC", "DLR",
    "AVB", "EQR", "VTR", "WY", "MAA", "ARE", "KIM", "CLI", "STAG",
    "NTRS", "FULT", "BANF", "ONB", "RNR", "STL", "CBSH", "OFG",
    "AMGN", "GILD", "VRTX", "BIIB", "REGN", "MRNA", "NVAX",
    "XOM", "CVX", "COP", "EOG", "SLB", "HAL", "BKR", "SLB",
    "PSX", "VLO", "MPC", "PSX", "HES", "FANG", "MRO", "DVN",
    "PXD", "EOG", "OXY", "MUR", "FANG", "HES",
    "CAT", "DE", "JCI", "ETN", "EMR", "FTNT", "SWK", "ROK",
    "GWW", "ITW", "MMM", "DOV", "PH", "CTAS", "TDG", "LHX", "LMT", "BAE",
    "GD", "NOC", "RTX", "BA", "UPS", "FDX", "CSX", "NSC", "UNP",
    "FDX", "UPS", "DHL", "XPO", "CHRW", "JBHT", "EXPD", "ODFL",
    "AMT", "PLD", "CCI", "PSA", "EQIX", "O", "SBAC", "SPG", "DLR",
    "WY", "EQR", "VTR", "ARE", "KIM", "AVB", "MAA", "STAG", "CLI",
    "GLW", "KEYS", "ANET", "CDW", "EPAM", "MPWR", "GEN", "CDNS", "SNPS",
    "LRCX", "AMAT", "ASML", "KLAC", "TER", "MPWR", "ON", "MRVL", "MU",
    "AVGO", "QCOM", "AMD", "INTC", "NVDA", "META", "GOOGL", "AMZN", "AAPL",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK.B",
    "JPM", "UNH", "XOM", "MA", "V", "PG", "HD", "CVX", "MRK",
    "ABBV", "PEP", "KO", "WMT", "TMO", "MCD", "CSCO", "ACN", "ABT",
    "CRM", "ADBE", "DHR", "NEE", "TXN", "PM", "NKE", "ORCL",
    "BMY", "UNP", "INTU", "AMGN", "HON", "QCOM", "LOW", "AMAT", "SPGI",
    "CAT", "DE", "ELV", "GILD", "BKNG", "ISRG", "ADI", "SBUX", "MMM", "AXP",
    "LRCX", "MMC", "TJX", "MDT", "VRTX", "NOW", "PFE", "ZTS", "BLK", "SYK",
    "SCHW", "CI", "CB", "SO", "DUK", "CCI", "AMT", "PLD", "SBAC",
    "EQIX", "PSA", "O", "MSCI", "USB", "CME", "ICE", "AON", "MCO",
    "PGR", "RE", "TGT", "ETN", "EMR", "CARR", "GD", "PH", "CTAS", "WM",
    "CSX", "NSC", "FDX", "RTX", "UPS", "BA", "LMT", "NOC", "LHX",
    "HON", "GE", "ITW", "SWK", "FTNT", "JCI", "RSG", "PHM", "DHI", "LEN",
    "PPG", "APD", "ECL", "SHW", "DD", "FCX", "NUE", "STLD", "DOW", "CE",
    "LYB", "ALB", "CTVA", "FMC", "CF", "MOS", "NTR", "SCCO", "VMC", "MLM",
    "FAST", "MSM", "CPRT", "PCAR", "ODFL", "CHRW", "JBHT", "CARR", "TT",
    "EXPD", "GWW", "DOV", "XYL", "ROK", "FTV", "AME", "DCI", "IEX",
    "TDG", "HEI", "TEL", "ANET", "CDW", "EPAM", "MPWR", "KEYS", "TER",
    "ANSS", "SNPS", "CDNS", "CAD", "FORM", "FDS", "GEN", "GLW", "COF",
    "DFS", "BAC", "GS", "MS", "C", "BLK", "AMP", "TFC", "CFG", "STT",
    "SYF", "AFL", "MET", "PRU", "AIG", "TRV", "WRB", "HIG", "CINF",
    "FIS", "FISV", "GPN", "PYPL", "SQ", "WFC", "PNC", "MTB", "KEY", "HBAN",
    "RF", "CMA", "ABC", "JNJ", "LLY", "PFE", "ABBV", "MRK", "BMY", "AMGN",
    "GILD", "VRTX", "BIIB", "REGN", "MRNA", "NVAX", "XOM", "CVX", "COP",
    "EOG", "SLB", "HAL", "BKR", "PSX", "VLO", "MPC", "HES", "FANG", "MRO",
    "DVN", "PXD", "OXY", "MUR", "JCI", "ETN", "EMR", "ROK", "PH", "CTAS",
    "TDG", "LHX", "LMT", "NOC", "RTX", "BA", "GD", "UPS", "FDX", "UNP",
    "NSC", "JBHT", "EXPD", "ODFL", "GLW", "KEYS", "ANET", "CDW", "EPAM",
    "MPWR", "GEN", "CDNS", "SNPS", "LRCX", "AMAT", "ASML", "KLAC", "TER",
    "ON", "MRVL", "MU", "AVGO", "QCOM", "AMD", "INTC", "NVDA", "META",
    "GOOGL", "AMZN", "AAPL", "MSFT", "ORCL", "IBM", "CSCO", "ACN", "NOW",
    "INTU", "ADBE", "PYPL", "SHOP", "SQ", "SNOW", "DDOG", "CRWD", "NET",
    "OKTA", "ZS", "HUBS", "TEAM", "DOCU", "ZM", "FIS", "FISV", "GPN",
]


def load_seed_universe() -> list[str]:
    return sorted(set(SEED_UNIVERSE))


def save_seed_csv(path: Path, symbols: list[str] | None = None) -> None:
    if symbols is None:
        symbols = load_seed_universe()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("symbol\n")
        for s in sorted(set(symbols)):
            f.write(f"{s}\n")


if __name__ == "__main__":
    save_seed_csv(Path(__file__).parent.parent / "data" / "seed_universe.csv")
