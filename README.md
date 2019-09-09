
# Intro

This is a simulate simulation of a buy-and-hold portfolio that tracks the S&P500 and spends a fixed (real) percentage of the original investment amount every year.


# Caveats

The current version of the code isn't taking dividends into account, so as it is now, it's going to produce pessimistic results.

The code here isn't clean. It was whipped up quickly, and the results were used as a conversation topic in a forum. 

Hopefully I'll get time to fix the dividends problem and make it cleaner, and/or there will be pull requests for the same.


# Running

First, setup the virtualenv: `./create_virtualenv`

Then, source the virtualenv: `source ./source_virtualenv`

To do a basic run: `./investment.py --spending_percentage 3 sim-buy-and-hold --num_years 30`

To get more detailed output on what happened each year, add `-v` in front: `./investment.py -v --spending_percentage 3 sim-buy-and-hold --num_years 30`

If you want it to dump out data into csv files, use the `--output_csv_prefix` option: `./investment.py --spending_percentage 3 sim-buy-and-hold --num_years 30 --output_csv_file /tmp/output`



# License (MIT)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


