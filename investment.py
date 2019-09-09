#!/usr/bin/env python
from datetime import date, datetime
import csv
import logging
import math
import re
from typing import Dict, List, Optional, Tuple

import click
import click_log
import pandas as pd
from tabulate import tabulate
from termcolor import colored


logger = logging.getLogger(__name__)
click_log.basic_config(logger)


# We spend this much of the starting value of the portfolio per year.
SPENDING_PERCENTAGE = None

# Should we withdraw a fixed (real) amount each year, or always take a fixed percentage of
# the total value?
SPEND_FIXED_REAL_AMOUNT = None

# How much money the strategies start with. This just needs to be some high multiple of the
# share price.
STARTING_CASH = 1e6



@click.group()
@click.option('-v', default=False, is_flag=True)
@click.option('--spending_percentage', type=float, default=4)
@click.option('--spend_fixed_real_amount/--no_spend_fixed_real_amount', default=True, is_flag=True)
def cli(v, spending_percentage: float, spend_fixed_real_amount: bool):
    if v:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    global SPENDING_PERCENTAGE
    SPENDING_PERCENTAGE = spending_percentage / 100

    global SPEND_FIXED_REAL_AMOUNT
    SPEND_FIXED_REAL_AMOUNT = spend_fixed_real_amount



def get_inflation_data() -> Dict[int, float]:
    """
    Load the inflation history so we have an inflation rate per year.

    Return:
        A dictionary mapping the year to the inflation rate for that year.
    """
    # Inflation data is from https://inflationdata.com/inflation/inflation_rate/historicalinflation.aspx
    ret = {}
    data = pd.read_csv('inflation_history.csv')
    for outer_row in data.iterrows():
        row = outer_row[1]
        total = 0
        num_good = 0
        for month in 'Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec'.split(','):
            cur = row[month]
            if isinstance(cur, str):
                num_good += 1
                total += float(cur.replace('%', '')) / 100

        # If any of the values were bad, then rescale as though it were only N months.
        total *= (12 / num_good)
        total /= 12
        ret[row['Year']] = total
    return ret

year_to_inflation = get_inflation_data()

#
# Process the S&P data.
# S&P500 data is from https://finance.yahoo.com/quote/%5EGSPC/history
#
snp = pd.read_csv('snp_history.csv', header=0)

yearly_prices = {}
all_dates = [(datetime.strptime(row[1]['Date'], '%Y-%m-%d').date(), row[1]) for row in snp.iterrows()]

class SnpYear:
    def __init__(self, year: int, open: float, close: float):
        self.year = year
        self.open = open
        self.close = close

snp_yearly = {}
for year in sorted(set(x[0].year for x in all_dates)):
    samples = [x for x in all_dates if x[0].year == year]
    open_entry = min(samples, key=lambda x: x[0])[1]
    close_entry = max(samples, key=lambda x: x[0])[1]

    snp_yearly[year] = SnpYear(year, open_entry['Open'], close_entry['Close'])



class Market:
    """Provides market pricing data.
    """
    def __init__(self, snp_yearly, start_year: int, year_to_inflation: Dict[int, float]):
        self._cur_year = start_year
        self._at_start_of_year = True
        self._snp_yearly = snp_yearly
        self._year_to_inflation = year_to_inflation

    def move_to_next_year(self):
        self._cur_year += 1
        self._at_start_of_year = True

    def move_to_end_of_current_year(self):
        self._at_start_of_year = False

    @property
    def current_inflation(self) -> float:
        return self._year_to_inflation[self._cur_year]

    @property
    def current_year_growth(self) -> float:
        """
        Return:
            The percentage growth of the S&P500's nominal price in the current year.
        """
        return (self._snp_yearly[self._cur_year].close - self._snp_yearly[self._cur_year].open) / self._snp_yearly[self._cur_year].open
    
    @property
    def current_price(self):
        if self._at_start_of_year:
            return self._snp_yearly[self._cur_year].open
        else:
            return self._snp_yearly[self._cur_year].close


class InvestmentAccount:
    """This simulates an investment account that strategies can operate on.
    """
    def __init__(self, starting_cash: float, market: Market):
        self._cash = starting_cash
        self._market = market
        self._num_shares = 0

    @property
    def cash_available(self) -> float:
        return self._cash

    def buy_stock(self, num_shares: int):
        logger.debug(f'\tbuy {num_shares} at {self._market.current_price}')
        assert self._cash >= self._market.current_price * num_shares
        self._cash -= self._market.current_price * num_shares
        self._num_shares += num_shares

    def sell_stock(self, num_shares: int) -> bool:
        logger.debug(f'\tsell {num_shares} at {self._market.current_price}, {self._num_shares - num_shares} remaining, worth ${self.net_worth:.2f}')
        if self._num_shares < num_shares:
            return False

        self._cash += self._market.current_price * num_shares
        self._num_shares -= num_shares
        return True

    def spend_cash(self, amount: float) -> bool:
        if self._cash < amount:
            return False
        self._cash -= amount
        return True

    @property
    def num_shares_owned(self):
        return self._num_shares
    
    @property
    def net_worth(self) -> float:
        """
        Return:
            The net worth of the account. This is usually the nominal value in whatever year
            the simulation is currently in.
        """
        return self._cash + self._num_shares * self._market.current_price


class Strategy:
    def __init__(self):
        self._output_csv_prefix = None

    def go(self, account: InvestmentAccount, market: Market, start_year: int, num_years: int) -> Tuple[bool, str]:
        raise('Strategy.go not implemented')

    def set_output_csv_prefix(self, output_csv_prefix: Optional[str]):
        self._output_csv_prefix = output_csv_prefix


def dollarstr(amount: float) -> str:
    return f'${amount:,.0f}'

def dollarstr_decimal(amount: float) -> str:
    return f'${amount:,.2f}'

def percentstr(percent: float) -> str:
    return f'{percent * 100:.2f}%'

ANSI_ESCAPE = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
def remove_ansi_codes(string: str):
    return ANSI_ESCAPE.sub('', string)


def write_table_to_csv(table: List[List], filename: str):
    """Write a list-of-lists to a csv file.

    Args:
        table: The list-of-lists to write to the table.

        filename: The output filename.
    """
    with open(filename, 'w') as csvfile:
        writer = csv.writer(csvfile, delimiter='\t')
        for row in table:
            writer.writerow(row)


class BuyAndHoldStrategy(Strategy):
    """This strategy invests all the money into shares of S&P500, then sells only enough to
    fund a certain inflation-adjusted percentage of the original portfolio amount each year.
    """
    def go(self, account: InvestmentAccount, market: Market, start_year: int, num_years: int) -> Tuple[bool, str]:
        logger.debug(f'Simulating {start_year} - {start_year + num_years}')

        fixed_real_withdrawal = account.cash_available * SPENDING_PERCENTAGE

        # Invest everything right away.
        account.buy_stock(math.floor(account.cash_available / market.current_price))

        debug_info = [[
            'year', 

            'start # shares',
            'start net worth\n(nominal)',

            'start-of-year\nwithdrawal\n(inflation-adjusted cash to spend)',
            'start-of-year\nwithdrawal\n(shares sold)',
            'unspent cash',

            'start share price',
            'end share price',

            'inflation %', 
            
            'end # shares',
            'end net worth\n(nominal)',]]

        ret = (True, '')
        for year in range(start_year, start_year + num_years):
            start_shares = account.num_shares_owned
            start_net_worth = account.net_worth

            constant_percent_withdrawal = account.net_worth * SPENDING_PERCENTAGE

            if SPEND_FIXED_REAL_AMOUNT:
                this_year_withdrawal = fixed_real_withdrawal
            else:
                this_year_withdrawal = constant_percent_withdrawal

            # At the end of each year, sell enough to get us our yearly withdrawal.
            num_shares_to_sell = math.ceil((this_year_withdrawal - account.cash_available) / market.current_price)
            if not account.sell_stock(num_shares_to_sell):
                ret = (False, colored(f'ran short in {year}', 'red'))
                logger.debug(f'\tDOH: {ret[1]}')
                break

            if not account.spend_cash(this_year_withdrawal):
                ret = (False, colored('failed to spend cash?', 'yellow'))
                logger.debug(f'\tDOH: {ret[1]}')
                break

            start_share_price = market.current_price

            market.move_to_end_of_current_year()

            debug_info.append([
                year,

                start_shares,
                dollarstr(start_net_worth),

                dollarstr(this_year_withdrawal),
                num_shares_to_sell,
                dollarstr(account.cash_available),

                dollarstr_decimal(start_share_price),
                dollarstr_decimal(market.current_price),

                percentstr(market.current_inflation),

                account.num_shares_owned,
                dollarstr(account.net_worth)
            ])

            # Inflation-adjust our fixed withdrawal rate. We do this AFTER applying the withdrawal
            # rate, since we withdrew the money at the beginning of the year, before this year's
            # inflation had been applied.
            fixed_real_withdrawal *= (1 + market.current_inflation)

            market.move_to_next_year()


        logger.debug(tabulate(debug_info, headers='firstrow') + '\n\n')
        if self._output_csv_prefix is not None:
            write_table_to_csv(debug_info, self._output_csv_prefix)

        return ret


def get_inflation_percentage(start_year: int, num_years: int) -> float:
    """
    Args:
        start_year: The first year to apply inflation from.

        num_years: How many years to apply inflation from.

    Return:
        The percentage of inflation experienced between the given years.
    """
    percent = 1
    for year in range(start_year, start_year + num_years):
        percent *= (1 + year_to_inflation[year])
    return percent


def nominal_to_real(start: float, start_year: int, num_years: int) -> float:
    """Take a nominal input value, and apply inflation from the specified year range
    to get the real value of that money at the end of the period.

    Args:
        start: The starting (nominal) value.

        start_year: The first year to apply inflation from.

        num_years: How many years to apply inflation from.

    Return:
        The real value of that money after inflation was applied.
    """
    return start * (1. / get_inflation_percentage(start_year, num_years))




def run_strategy(strategy_class, start_years: List[int], num_years: int, output_csv_prefix: Optional[str]):
    """This runs one simulation per start year that you give it. Each simulation goes for `num_years` years.

    Args:
        strategy_class: This is any class that derives from Strategy. It is the thing that will
                        make the buy, sell, and spending decisions over time.

        start_years: One simulation will be run for each entry in this list, starting on that year.

        num_years: Each simulation will run for this many years.

        output_csv_prefix: If this is not None, then a bunch of csv files will be dumped out with
                           filenames with this prefix.
    """

    display = [['Years', 'End value (real)', 'End value (nominal)', 'Gain', 'Inflation']]
    for year in start_years:
        # Create the market and investment account.
        market = Market(snp_yearly, year, year_to_inflation)
        account = InvestmentAccount(STARTING_CASH, market)

        # Create the Strategy instance.
        # (We instantiate a Strategy for each start date that we're going to simulate).
        strategy = strategy_class()

        if output_csv_prefix is not None:
            strategy.set_output_csv_prefix(output_csv_prefix + f'_for_year_{year}.csv')

        years_range = f'{year} - {year + num_years}'

        # Run the strategy.
        status = strategy.go(account, market, year, num_years)
        if status[0]:
            inflation = get_inflation_percentage(year, num_years)

            # For reporting of the outcome, convert nominal dollars to real (starting year) dollars.
            net_worth_real = nominal_to_real(account.net_worth, year, num_years)
            
            # Did we gain or lose?
            remainder_percent = (net_worth_real - STARTING_CASH) * 100 / STARTING_CASH

            if remainder_percent > 0:
                gainloss = [f'{remainder_percent:.2f}%']
            else:
                gainloss = [colored(f'{remainder_percent:.2f}%', 'red')]

            display += [[years_range, f'${net_worth_real:,.0f}', f'${account.net_worth:,.0f}'] + gainloss + [f'{inflation*100:.2f}%']]
        else:
            display += [[years_range, status[1], '', '', '', '']]

    # Debug output.        
    logger.info(tabulate(display, headers='firstrow'))
    if output_csv_prefix is not None:
        stripped = [[remove_ansi_codes(i) for i in line] for line in display]
        write_table_to_csv(stripped, output_csv_prefix + '_summary.csv')


@cli.command()
@click.option('--num_years', type=int, default=30, show_default=True,
    help='How many years to run each simulation for. The longer this is, the further back in time it has to start from present day. ' + \
         '(i.e. if you specify 50 here, then in 2019, the last start date it could run from would be 2019-50 (1969), because it doesn\'t ' + \
         'have any data past 2019.')
@click.option('--only_year', type=int, default=None, show_default=True, help='If you specify this parameter, it will only run a simulation starting on this year.')
@click.option('--output_csv_prefix', type=str, default=None, help='BASE filename (without extension) for debug csv files', show_default=True)
def sim_buy_and_hold(num_years: int, only_year: Optional[int], output_csv_prefix: Optional[str]):
    """This command simulates a portfolio starting in every possible year (that we have data for)
    that goes for num_years.
    """
    start_years = []

    if only_year is None:
        # If they haven't specified a single start year to try, then do all the years we can.
        years = sorted(set(snp_yearly.keys()))
        for iyear in range(len(years) - num_years):
            start_years.append(years[iyear])
    else:
        start_years = [only_year]

    run_strategy(BuyAndHoldStrategy, start_years, num_years, output_csv_prefix)

    if output_csv_prefix is not None:
        # Write out the inflation data.
        inflation_table = [['Year', 'Inflation %']]
        for year in sorted(year_to_inflation.keys()):
            inflation_table.append([year, f'{year_to_inflation[year] * 100}%'])
        write_table_to_csv(inflation_table, output_csv_prefix + '_inflation.csv')

        # Write the yearly market data.
        market_table = [['Year', 'Open', 'Close']]
        for year in sorted(snp_yearly.keys()):
            market_table.append([year, snp_yearly[year].open, snp_yearly[year].close])
        write_table_to_csv(market_table, output_csv_prefix + '_snp_prices.csv')


if __name__ == '__main__':
    cli()
