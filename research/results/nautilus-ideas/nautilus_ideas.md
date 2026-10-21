# Nautilus example rules on the point-in-time S&P 500

Price coverage of member-days by year: 2013 0%, 2014 16%, 2015 71%, 2016 74%, 2017 77%, 2018 78%, 2019 81%, 2020 84%, 2021 86%, 2022 89%, 2023 91%, 2024 92%, 2025 93%, 2026 94%

## ema: FAILS (2015-07-22 to 2026-08-18)

- all: alpha +0.7%/yr (t +0.37), beta 0.34, Sharpe 0.62 vs 0.73, max DD -13.0% vs -39.9%, return 5.2% vs 13.5%
- first_half: alpha +1.0%/yr (t +0.34), beta 0.30, Sharpe 0.56 vs 0.66, max DD -11.4% vs -39.9%, return 5.0% vs 13.7%
- second_half: alpha -0.0%/yr (t -0.00), beta 0.41, Sharpe 0.69 vs 0.85, max DD -13.0% vs -21.0%, return 5.5% vs 13.6%
- without_best_year: alpha -0.5%/yr (t -0.44), beta 0.41, Sharpe 0.64 vs 0.85, max DD -13.0% vs -21.0%, return 4.7% vs 12.8%
- without_2020: alpha -0.5%/yr (t -0.44), beta 0.41, Sharpe 0.64 vs 0.85, max DD -13.0% vs -21.0%, return 4.7% vs 12.8%
- best year: 2020
- by year (alpha/yr): 2015 -8.5%, 2016 -0.8%, 2017 -0.5%, 2018 -4.3%, 2019 -0.6%, 2020 +5.5%, 2021 -1.9%, 2022 -6.0%, 2023 +2.9%, 2024 -2.0%, 2025 -1.8%, 2026 +1.4%

- FAIL alpha>0 and t>=2.5
- FAIL both halves positive
- FAIL positive without best year
- FAIL positive without 2020

## dch: FAILS (2015-07-22 to 2026-08-18)

- all: alpha +0.2%/yr (t +0.12), beta 0.24, Sharpe 0.52 vs 0.73, max DD -10.5% vs -39.9%, return 3.4% vs 13.5%
- first_half: alpha +0.3%/yr (t +0.13), beta 0.21, Sharpe 0.45 vs 0.66, max DD -10.5% vs -39.9%, return 3.2% vs 13.7%
- second_half: alpha -0.2%/yr (t -0.17), beta 0.28, Sharpe 0.60 vs 0.85, max DD -8.1% vs -21.0%, return 3.7% vs 13.6%
- without_best_year: alpha -0.1%/yr (t -0.09), beta 0.23, Sharpe 0.45 vs 0.70, max DD -10.5% vs -39.9%, return 3.0% vs 13.4%
- without_2020: alpha -0.1%/yr (t -0.15), beta 0.28, Sharpe 0.62 vs 0.85, max DD -9.0% vs -21.0%, return 3.4% vs 12.8%
- best year: 2023
- by year (alpha/yr): 2015 -5.8%, 2016 +0.3%, 2017 -0.9%, 2018 -3.5%, 2019 +2.1%, 2020 -0.3%, 2021 -1.5%, 2022 -0.8%, 2023 +2.5%, 2024 -3.2%, 2025 -2.4%, 2026 -1.2%

- FAIL alpha>0 and t>=2.5
- FAIL both halves positive
- FAIL positive without best year
- FAIL positive without 2020

