# Aperiodic Factors Client

A Python client library for the [Aperiodic Factors](https://factors.aperiodic.io)
API, providing convenient wrappers for cross-sectional crypto factor data,
portfolio weights/returns and risk signals.

This package lives inside the data-room repository as a vendored module — it is
**not** published to PyPI. The notebooks and scripts in this repository depend
on it via the importable `aperiodic` package.

## Installation

From the repository root:

```bash
pip install ./aperiodic-factors-client
```

(`requirements.txt` already installs it for you.)

## Features

- **Portfolio Data**: Access historical and live portfolio weights
- **Cross-section Factors**: Access cross-sectional factors as raw data
- **Risk Signals**: Retrieve normalized risk factor series for cryptocurrencies
- **Easy Integration**: Simple API calls with pandas DataFrame/Series returns

## Quick Start

```python
import aperiodic

# Set your API key
api_key = "your-api-key-here"

# Get historical portfolio weights
historical_weights = aperiodic.get_portfolio_historical_weights(
    id="your-portfolio-id",
    api_key=api_key,
    start_date="2024-01-01",
    end_date="2024-12-31",
)

# Get current portfolio weights
live_weights = aperiodic.get_live_weights(
    id="your-portfolio-id",
    api_key=api_key,
)

# Get portfolio returns
returns = aperiodic.get_portfolio_returns(
    id="your-portfolio-id",
    api_key=api_key,
    start_date="2024-01-01",
)

# Get portfolio tickers
tickers = aperiodic.get_tickers(
    id="momentum",  # Portfolio factor identifier without universe specifier
    api_key=api_key,
    universe_size="full",
)

# Get historical factors
factors = aperiodic.get_portfolio_factors_historical(
    id="momentum",
    tickers=["BTC", "ETH"],
    api_key=api_key,
)

# Get live factors (latest factor data)
live_factors = aperiodic.get_portfolio_factors_live(
    id="momentum",
    tickers=["BTC", "ETH"],
    api_key=api_key,
)

# Get historical universe
universe = aperiodic.get_historical_universe(
    size="full",
    start_date="2024-01-01",
    end_date="2024-12-31",
    api_key=api_key,
)
```

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `APERIODIC_API_KEY` | yes | — | Your Aperiodic Factors API key |
| `APERIODIC_BASE_URL` | no | `https://factors.aperiodic.io` | Override the API base URL |
| `CF_ACCESS_CLIENT_ID` | no | — | Cloudflare Access service-token id (protected environments) |
| `CF_ACCESS_CLIENT_SECRET` | no | — | Cloudflare Access service-token secret |

## Requirements

- Python 3.9+
- pandas >= 2.0.0
- numpy >= 1.3.0
- requests >= 2.25.0

## Testing

The test suite exercises the live API, so it needs a valid API key. Tests that
require it are skipped automatically when `APERIODIC_API_KEY` is not set.

```bash
# Install with test dependencies
pip install -e ".[tests]"

# Run all tests
export APERIODIC_API_KEY="your_api_key_here"
pytest tests/ -v
```

## License

MIT License
