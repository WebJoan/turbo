# Import necessary libraries and modules for stock analysis workflow
from agno.agent.agent import Agent  # Core agent functionality
from agno.models.openai.chat import OpenAIChat  # OpenAI chat model integration
from agno.workflow.v2 import Step, Workflow, StepOutput  # Workflow management components
from ag_ui.core import EventType, StateDeltaEvent  # Event handling for UI updates
from ag_ui.core import AssistantMessage, ToolMessage  # Message types for chat interface
import uuid  # For generating unique identifiers
import asyncio  # For asynchronous operations
from openai import OpenAI  # OpenAI API client
from dotenv import load_dotenv  # For loading environment variables
import os  # Operating system interface
import json  # JSON data handling
import yfinance as yf  # Yahoo Finance API for stock data
from datetime import datetime  # Date and time handling
import numpy as np  # Numerical computing
import pandas as pd  # Data manipulation and analysis
from prompts import insights_prompt, system_prompt  # Custom prompt templates

# Load environment variables from .env file (contains API keys, etc.)
load_dotenv()


# Tool function definition: Extract investment parameters from user input
# This tool allows the AI to parse user requests and extract structured data like:
# - Stock ticker symbols (e.g., AAPL, GOOGL)
# - Investment amounts in dollars
# - Investment dates and intervals
# - Portfolio preferences (main vs sandbox)
extract_relevant_data_from_user_prompt = {
    "type": "function",  # <--- REQUIRED in `tools` list
    "function": {
        "name": "extract_relevant_data_from_user_prompt",
        "description": "Gets the data like ticker symbols, amount of dollars to be invested, interval of investment.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker_symbols": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "A list of stock ticker symbols, e.g. ['AAPL', 'GOOGL']."
                },
                "investment_date": {
                    "type": "string",
                    "description": "The date of investment, e.g. '2023-01-01'.",
                    "format": "date"
                },
                "amount_of_dollars_to_be_invested": {
                    "type": "array",
                    "items": {
                        "type": "number"
                    },
                    "description": "The amount of dollars to be invested, e.g. [10000, 20000, 30000]."
                },
                "interval_of_investment": {
                    "type": "string",
                    "description": "The interval of investment, e.g. '1d', '5d', '1mo', '3mo', '6mo', '1y'. If the user did not specify the interval, assume it as 'single_shot'.",
                    "enum": ["1d", "5d", "7d", "1mo", "3mo", "6mo", "1y", "2y", "3y", "4y", "5y", "single_shot"]
                },
                "to_be_added_in_portfolio": {
                    "type": "boolean",
                    "description": "True if the user wants to add it to the current portfolio; false if they want to add it to the sandbox portfolio."
                }
            },
            "required": [
                "ticker_symbols",
                "investment_date",
                "amount_of_dollars_to_be_invested",
                "to_be_added_in_portfolio"
            ]
        }
    }
}

# Tool function definition: Generate bull/bear market insights
# This tool creates positive and negative market analysis for stocks/portfolios
# Each insight includes a title, detailed description, and emoji for UI display
generate_insights = {
  "type": "function",
  "function": {
    "name": "generate_insights",
    "description": "Generate positive (bull) and negative (bear) insights for a stock or portfolio.",
    "parameters": {
      "type": "object",
      "properties": {
        "bullInsights": {
          "type": "array",
          "description": "A list of positive insights (bull case) for the stock or portfolio.",
          "items": {
            "type": "object",
            "properties": {
              "title": {
                "type": "string",
                "description": "Short title for the positive insight."
              },
              "description": {
                "type": "string",
                "description": "Detailed description of the positive insight."
              },
              "emoji": {
                "type": "string",
                "description": "Emoji representing the positive insight."
              }
            },
            "required": ["title", "description", "emoji"]
          }
        },
        "bearInsights": {
          "type": "array",
          "description": "A list of negative insights (bear case) for the stock or portfolio.",
          "items": {
            "type": "object",
            "properties": {
              "title": {
                "type": "string",
                "description": "Short title for the negative insight."
              },
              "description": {
                "type": "string",
                "description": "Detailed description of the negative insight."
              },
              "emoji": {
                "type": "string",
                "description": "Emoji representing the negative insight."
              }
            },
            "required": ["title", "description", "emoji"]
          }
        }
      },
      "required": ["bullInsights", "bearInsights"]
    }
  }
}

# WORKFLOW STEP 1: Initial chat processing and parameter extraction
# This function handles the first interaction with the user query
async def chat(step_input):
    try:
        # Step 1: Initialize tool logging for UI feedback
        # Generate unique ID for tracking this operation
        tool_log_id = str(uuid.uuid4())
        
        # Step 2: Add processing status to tool logs
        # This shows "Analyzing user query" status in the UI
        step_input.additional_data['tool_logs'].append({
            "message": "Analyzing user query",
            "status": "processing",
            "id": tool_log_id,
        })
        
        # Step 3: Emit state change event to update UI
        # Uses JSON patch operations to update the frontend state
        step_input.additional_data["emit_event"](
            StateDeltaEvent(
                type=EventType.STATE_DELTA,
                delta=[
                    {
                        "op": "add",  # Add new log entry
                        "path": "/tool_logs/-",  # Append to tool_logs array
                        "value": {
                            "message": "Analyzing user query",
                            "status": "processing",
                            "id": tool_log_id,
                        },
                    }
                ],
            )
        )
        await asyncio.sleep(0)  # Yield control to event loop
        
        # Step 4: Prepare system prompt with portfolio data
        # Replace placeholder in system prompt with actual portfolio information
        step_input.additional_data['messages'][0].content = system_prompt.replace(
            "{PORTFOLIO_DATA_PLACEHOLDER}", json.dumps(step_input.additional_data["investment_portfolio"])
        )
        
        # Step 5: Make API call to OpenAI
        # Initialize OpenAI client with API key from environment
        model = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Step 6: Request completion with tool calling capability
        # The model can call the extract_relevant_data_from_user_prompt tool
        response = model.chat.completions.create(
            model="gpt-4.1-mini",  # Use GPT-4 mini model
            messages= step_input.additional_data['messages'],  # Chat history
            tools= [extract_relevant_data_from_user_prompt]  # Available tools
        )
        
        # Step 7: Update tool log status to completed
        # Find the last log entry and mark it as completed
        index = len(step_input.additional_data['tool_logs']) - 1
        step_input.additional_data["emit_event"](
            StateDeltaEvent(
                type=EventType.STATE_DELTA,
                delta=[
                    {
                        "op": "replace",  # Update existing value
                        "path": f"/tool_logs/{index}/status",
                        "value": "completed",
                    }
                ],
            )
        )
        await asyncio.sleep(0)  # Yield control to event loop
        
        # Step 8: Process the AI response
        # Check if the AI decided to call a tool (function)
        if(response.choices[0].finish_reason == "tool_calls"):
            # Convert tool calls to our internal format
            tool_calls = [
                convert_tool_call(tc)
                for tc in response.choices[0].message.tool_calls
            ]
            # Create assistant message with tool calls
            a_message = AssistantMessage(
                role="assistant", tool_calls=tool_calls, id=response.id
            )
            step_input.additional_data["messages"].append(a_message)
        else:
            # If no tool calls, just add the text response
            a_message = AssistantMessage(
                id=response.id,
                content=response.choices[0].message.content,
                role="assistant",
            )
            step_input.additional_data["messages"].append(a_message)
        
        # Step 9: Return updated data for next workflow step
        return step_input.additional_data
            
    except Exception as e:
        # Step 10: Handle errors gracefully
        print(e)  # Log error for debugging
        # Add empty assistant message to maintain conversation flow
        a_message = AssistantMessage(id=response.id, content="", role="assistant")
        step_input.additional_data["messages"].append(a_message)
        return "end"  # Signal workflow termination


# WORKFLOW STEP 2: Stock data simulation and gathering
# This function retrieves historical stock data based on extracted parameters
async def simultion(step_input):
    # Step 1: Check if previous step generated tool calls
    # If no tool calls, skip this step (no parameters to process)
    # Step 1: Check if previous step generated tool calls
    # If no tool calls, skip this step (no parameters to process)
    if step_input.additional_data["messages"][-1].tool_calls is None:
        return
    
    # Step 2: Initialize tool logging for stock data gathering
    tool_log_id = str(uuid.uuid4())
    step_input.additional_data["tool_logs"].append(
        {
            "id": tool_log_id,
            "message": "Gathering Stock Data",
            "status": "processing",
        }
    )
    
    # Step 3: Emit UI update event for data gathering status
    step_input.additional_data["emit_event"](
        StateDeltaEvent(
            type=EventType.STATE_DELTA,
            delta=[
                {
                    "op": "add",
                    "path": "/tool_logs/-",
                    "value": {
                        "message": "Gathering Stock Data",
                        "status": "processing",
                        "id": tool_log_id,
                    },
                }
            ],
        )
    )
    await asyncio.sleep(0)  # Yield control to event loop
    
    # Step 4: Parse extracted arguments from previous AI tool call
    # Convert JSON string back to Python dictionary
    arguments = json.loads(step_input.additional_data["messages"][-1].tool_calls[0].function.arguments)
    
    # Step 5: Create investment portfolio structure
    # Build array of ticker-amount pairs from extracted data
    step_input.additional_data["investment_portfolio"] = json.dumps(
        [
            {
                "ticker": ticker,  # Stock symbol
                "amount": arguments["amount_of_dollars_to_be_invested"][index],  # Investment amount
            }
            for index, ticker in enumerate(arguments["ticker_symbols"])
        ]
    )
    
    # Step 6: Update UI with investment portfolio information
    step_input.additional_data["emit_event"](
        StateDeltaEvent(
            type=EventType.STATE_DELTA,
            delta=[
                {
                    "op": "replace",
                    "path": f"/investment_portfolio",
                    "value": json.loads(step_input.additional_data["investment_portfolio"]),
                }
            ],
        )
    )
    await asyncio.sleep(2)  # Brief pause for UI update
    
    # Step 7: Process investment date and determine data range
    tickers = arguments["ticker_symbols"]  # Extract ticker symbols
    investment_date = arguments["investment_date"]  # Extract investment date
    current_year = datetime.now().year  # Get current year
    
    # Step 8: Validate and adjust investment date if too far in the past
    # Limit historical data to maximum 4 years for performance
    if current_year - int(investment_date[:4]) > 4:
        print("investment date is more than 4 years ago")
        investment_date = f"{current_year - 4}-01-01"  # Reset to 4 years ago
    
    # Step 9: Determine appropriate historical data period
    if current_year - int(investment_date[:4]) == 0:
        history_period = "1y"  # Current year: use 1 year
    else:
        history_period = f"{current_year - int(investment_date[:4])}y"  # Multi-year period

    # Step 10: Fetch historical stock data using yfinance
    # Download closing prices for specified tickers and date range
    data = yf.download(
        tickers,  # List of stock symbols
        # period=history_period,  # Commented out - using start/end instead
        interval="3mo",  # 3-month intervals for data points
        start=investment_date,  # Start date for data
        end=datetime.today().strftime("%Y-%m-%d"),  # End date (today)
    )
    
    # Step 11: Store retrieved data for next workflow steps
    step_input.additional_data["be_stock_data"] = data["Close"]  # Closing prices only
    step_input.additional_data["be_arguments"] = arguments  # Parsed arguments
    
    # Step 12: Mark data gathering as completed in UI
    index = len(step_input.additional_data["tool_logs"]) - 1
    step_input.additional_data["emit_event"](
        StateDeltaEvent(
            type=EventType.STATE_DELTA,
            delta=[
                {
                    "op": "replace",
                    "path": f"/tool_logs/{index}/status",
                    "value": "completed",
                }
            ],
        )
    )
    await asyncio.sleep(0)  # Yield control to event loop
    
    # Step 13: Return (no explicit return value needed)
    # Add your simulation logic here
    return


# WORKFLOW STEP 3: Cash allocation and portfolio simulation
# This function calculates how investments would perform over time
async def cash_allocation(step_input):
    # Step 1: Validate that we have tool calls to process
    if step_input.additional_data["messages"][-1].tool_calls is None:
        return
    
    # Step 2: Initialize tool logging for allocation calculation
    tool_log_id = str(uuid.uuid4())
    step_input.additional_data["tool_logs"].append(
        {
            "id": tool_log_id,
            "message": "Calculating portfolio allocation",
            "status": "processing",
        }
    )
    
    # Step 3: Emit UI update for allocation calculation status
    step_input.additional_data["emit_event"](
        StateDeltaEvent(
            type=EventType.STATE_DELTA,
            delta=[
                {
                    "op": "add",
                    "path": "/tool_logs/-",
                    "value": {
                        "message": "Allocating cash",
                        "status": "processing",
                        "id": tool_log_id,
                    },
                }
            ],
        )
    )
    await asyncio.sleep(0)  # Yield control to event loop
    
    # Step 4: Extract data from previous workflow steps
    stock_data = step_input.additional_data["be_stock_data"]  # DataFrame: index=date, columns=tickers
    args = step_input.additional_data["be_arguments"]  # Parsed user arguments
    tickers = args["ticker_symbols"]  # Stock symbols to invest in
    investment_date = args["investment_date"]  # When to start investing
    amounts = args["amount_of_dollars_to_be_invested"]  # list, one per ticker
    interval = args.get("interval_of_investment", "single_shot")  # Investment frequency

    # Step 5: Initialize cash and portfolio tracking variables
    # Use state['available_cash'] as a single integer (total wallet cash)
    if step_input.additional_data["available_cash"] is not None:
        total_cash = step_input.additional_data["available_cash"]  # Existing cash
    else:
        total_cash = sum(amounts)  # Sum of all investment amounts
    
    # Step 6: Initialize portfolio tracking structures
    holdings = {ticker: 0.0 for ticker in tickers}  # Shares owned per ticker
    investment_log = []  # Record of all transactions
    add_funds_needed = False  # Flag for insufficient funds
    add_funds_dates = []  # Dates when more funds were needed

    # Step 7: Ensure DataFrame is sorted chronologically
    # Ensure DataFrame is sorted by date
    stock_data = stock_data.sort_index()

    # Step 8: Handle different investment strategies
    if interval == "single_shot":
        # SINGLE SHOT INVESTMENT: Buy all shares at the first available date
        # Buy all shares at the first available date using allocated money for each ticker
        first_date = stock_data.index[0]  # Get first date in dataset
        row = stock_data.loc[first_date]  # Get prices for first date
        
        # Step 9: Process each ticker for single-shot investment
        for idx, ticker in enumerate(tickers):
            price = row[ticker]  # Current stock price
            
            # Step 10: Handle missing price data
            if np.isnan(price):
                investment_log.append(
                    f"{first_date.date()}: No price data for {ticker}, could not invest."
                )
                add_funds_needed = True
                add_funds_dates.append(
                    (str(first_date.date()), ticker, price, amounts[idx])
                )
                continue
            
            # Step 11: Calculate shares to purchase
            allocated = amounts[idx]  # Amount allocated to this ticker
            if total_cash >= allocated and allocated >= price:
                shares_to_buy = allocated // price  # Integer division for whole shares
                if shares_to_buy > 0:
                    cost = shares_to_buy * price  # Total cost
                    holdings[ticker] += shares_to_buy  # Update holdings
                    total_cash -= cost  # Reduce available cash
                    investment_log.append(
                        f"{first_date.date()}: Bought {shares_to_buy:.2f} shares of {ticker} at ${price:.2f} (cost: ${cost:.2f})"
                    )
                else:
                    # Step 12: Handle insufficient allocated funds
                    investment_log.append(
                        f"{first_date.date()}: Not enough allocated cash to buy {ticker} at ${price:.2f}. Allocated: ${allocated:.2f}"
                    )
                    add_funds_needed = True
                    add_funds_dates.append(
                        (str(first_date.date()), ticker, price, allocated)
                    )
            else:
                # Step 13: Handle insufficient total cash
                investment_log.append(
                    f"{first_date.date()}: Not enough total cash to buy {ticker} at ${price:.2f}. Allocated: ${allocated:.2f}, Available: ${total_cash:.2f}"
                )
                add_funds_needed = True
                add_funds_dates.append(
                    (str(first_date.date()), ticker, price, total_cash)
                )
        # No further purchases on subsequent dates
    else:
        # DOLLAR COST AVERAGING: Invest regularly over time
        # DCA or other interval logic (previous logic)
        for date, row in stock_data.iterrows():  # Iterate through all dates
            for i, ticker in enumerate(tickers):  # For each ticker
                price = row[ticker]  # Current price
                if np.isnan(price):
                    continue  # skip if price is NaN
                
                # Step 14: Invest as much as possible for this ticker at this date
                # Invest as much as possible for this ticker at this date
                if total_cash >= price:
                    shares_to_buy = total_cash // price  # Buy as many shares as possible
                    if shares_to_buy > 0:
                        cost = shares_to_buy * price
                        holdings[ticker] += shares_to_buy
                        total_cash -= cost
                        investment_log.append(
                            f"{date.date()}: Bought {shares_to_buy:.2f} shares of {ticker} at ${price:.2f} (cost: ${cost:.2f})"
                        )
                else:
                    # Step 15: Record when more funds are needed
                    add_funds_needed = True
                    add_funds_dates.append(
                        (str(date.date()), ticker, price, total_cash)
                    )
                    investment_log.append(
                        f"{date.date()}: Not enough cash to buy {ticker} at ${price:.2f}. Available: ${total_cash:.2f}. Please add more funds."
                    )

    # Step 16: Calculate final portfolio value and performance metrics
    # Calculate final value and new summary fields
    final_prices = stock_data.iloc[-1]  # Last row = most recent prices
    total_value = 0.0  # Total portfolio value
    returns = {}  # Absolute returns per ticker
    total_invested_per_stock = {}  # Amount invested per ticker
    percent_allocation_per_stock = {}  # Percentage allocation per ticker
    percent_return_per_stock = {}  # Percentage return per ticker
    total_invested = 0.0  # Total amount invested across all stocks
    
    # Step 17: Calculate investment amounts and returns for each ticker
    for idx, ticker in enumerate(tickers):
        # Calculate how much was actually invested in this stock
        if interval == "single_shot":
            # Only one purchase at first date
            first_date = stock_data.index[0]
            price = stock_data.loc[first_date][ticker]
            shares_bought = holdings[ticker]
            invested = shares_bought * price  # Total invested = shares * price
        else:
            # Sum all purchases from the log
            invested = 0.0
            for log in investment_log:
                if f"shares of {ticker}" in log and "Bought" in log:
                    # Extract cost from log string
                    try:
                        cost_str = log.split("(cost: $")[-1].split(")")[0]
                        invested += float(cost_str)
                    except Exception:
                        pass  # Skip if parsing fails
        total_invested_per_stock[ticker] = invested
        total_invested += invested  # Accumulate total invested
    
    # Step 18: Calculate percentage allocations and returns
    # Now calculate percent allocation and percent return
    for ticker in tickers:
        invested = total_invested_per_stock[ticker]  # Amount invested in this ticker
        holding_value = holdings[ticker] * final_prices[ticker]  # Current value
        returns[ticker] = holding_value - invested  # Absolute return
        total_value += holding_value  # Add to total portfolio value
        
        # Calculate percentage allocation (what % of total investment this represents)
        percent_allocation_per_stock[ticker] = (
            (invested / total_invested * 100) if total_invested > 0 else 0.0
        )
        
        # Calculate percentage return (profit/loss as percentage of invested amount)
        percent_return_per_stock[ticker] = (
            ((holding_value - invested) / invested * 100) if invested > 0 else 0.0
        )
    total_value += total_cash  # Add remaining cash to total value

    # Step 19: Store comprehensive investment summary
    # Store results in state
    step_input.additional_data["investment_summary"] = {
        "holdings": holdings,  # Shares owned per ticker
        "final_prices": final_prices.to_dict(),  # Current stock prices
        "cash": total_cash,  # Remaining cash
        "returns": returns,  # Absolute returns per ticker
        "total_value": total_value,  # Total portfolio value
        "investment_log": investment_log,  # Transaction history
        "add_funds_needed": add_funds_needed,  # Whether more funds needed
        "add_funds_dates": add_funds_dates,  # Dates/amounts when funds needed
        "total_invested_per_stock": total_invested_per_stock,  # Investment per ticker
        "percent_allocation_per_stock": percent_allocation_per_stock,  # Allocation %
        "percent_return_per_stock": percent_return_per_stock,  # Return %
    }
    step_input.additional_data["available_cash"] = total_cash  # Update available cash in state

    # Step 20: Calculate benchmark comparison with SPY (S&P 500)
    # --- Portfolio vs SPY performanceData logic ---
    # Get SPY prices for the same dates
    spy_ticker = "SPY"  # S&P 500 ETF ticker
    spy_prices = None
    try:
        # Step 21: Fetch SPY data for comparison
        spy_prices = yf.download(
            spy_ticker,
            # period=f"{len(stock_data)//4}y" if len(stock_data) > 4 else "1y",
            interval="3mo",  # Same interval as portfolio data
            start=stock_data.index[0],  # Same start date
            end=stock_data.index[-1],  # Same end date
        )["Close"]
        # Align SPY prices to stock_data dates
        spy_prices = spy_prices.reindex(stock_data.index, method="ffill")  # Forward fill
    except Exception as e:
        print("Error fetching SPY data:", e)
        # Create dummy data if SPY fetch fails
        spy_prices = pd.Series([None] * len(stock_data), index=stock_data.index)

    # Step 22: Simulate SPY investment with same strategy
    # Simulate investing the same total_invested in SPY
    spy_shares = 0.0  # SPY shares owned
    spy_cash = total_invested  # Start with same amount
    spy_invested = 0.0  # Amount actually invested in SPY
    spy_investment_log = []  # SPY transaction log
    
    if interval == "single_shot":
        # Step 23: Single-shot SPY investment
        first_date = stock_data.index[0]
        spy_price = spy_prices.loc[first_date]
        if isinstance(spy_price, pd.Series):
            spy_price = spy_price.iloc[0]  # Extract scalar value
        if not pd.isna(spy_price):
            spy_shares = spy_cash // spy_price  # Buy SPY shares
            spy_invested = spy_shares * spy_price  # Calculate cost
            spy_cash -= spy_invested  # Reduce cash
            spy_investment_log.append(
                f"{first_date.date()}: Bought {spy_shares:.2f} shares of SPY at ${spy_price:.2f} (cost: ${spy_invested:.2f})"
            )
    else:
        # Step 24: Dollar cost averaging SPY investment
        # DCA: invest equal portions at each date
        dca_amount = total_invested / len(stock_data)  # Amount per period
        for date in stock_data.index:
            spy_price = spy_prices.loc[date]
            if isinstance(spy_price, pd.Series):
                spy_price = spy_price.iloc[0]
            if not pd.isna(spy_price):
                shares = dca_amount // spy_price  # Shares to buy this period
                cost = shares * spy_price
                spy_shares += shares
                spy_cash -= cost
                spy_invested += cost
                spy_investment_log.append(
                    f"{date.date()}: Bought {shares:.2f} shares of SPY at ${spy_price:.2f} (cost: ${cost:.2f})"
                )

    # Step 25: Build performance comparison data
    # Build performanceData array
    performanceData = []  # Array for chart data
    running_holdings = holdings.copy()  # Copy holdings for calculation
    running_cash = total_cash
    
    for date in stock_data.index:
        # Step 26: Calculate portfolio value at each date
        # Portfolio value: sum of shares * price at this date + cash
        port_value = (
            sum(
                running_holdings[t] * stock_data.loc[date][t]
                for t in tickers
                if not pd.isna(stock_data.loc[date][t])  # Skip NaN prices
            )
            # + running_cash  # Commented out - not including cash in chart
        )
        
        # Step 27: Calculate SPY value at each date
        # SPY value: shares * price + cash
        spy_price = spy_prices.loc[date]
        if isinstance(spy_price, pd.Series):
            spy_price = spy_price.iloc[0]
        spy_val = (
            spy_shares * spy_price + spy_cash if not pd.isna(spy_price) else None
        )
        
        # Step 28: Add data point to performance array
        performanceData.append(
            {
                "date": str(date.date()),  # Convert to string for JSON
                "portfolio": float(port_value) if port_value is not None else None,
                "spy": float(spy_val) if spy_val is not None else None,
            }
        )

    # Step 29: Store performance data for chart rendering
    step_input.additional_data["investment_summary"]["performanceData"] = performanceData
    # --- End performanceData logic ---

    # Step 30: Generate summary message for user
    # Compose summary message
    if add_funds_needed:
        msg = "Some investments could not be made due to insufficient funds. Please add more funds to your wallet.\n"
        for d, t, p, c in add_funds_dates:
            msg += f"On {d}, not enough cash for {t}: price ${p:.2f}, available ${c:.2f}\n"
    else:
        msg = "All investments were made successfully.\n"
    
    msg += f"\nFinal portfolio value: ${total_value:.2f}\n"
    msg += "Returns by ticker (percent and $):\n"
    for ticker in tickers:
        percent = percent_return_per_stock[ticker]
        abs_return = returns[ticker]
        msg += f"{ticker}: {percent:.2f}% (${abs_return:.2f})\n"

    # Step 31: Add tool message to conversation
    step_input.additional_data["messages"].append(
        ToolMessage(
            role="tool",
            id=str(uuid.uuid4()),
            content="The relevant details had been extracted",  # Confirmation message
            tool_call_id=step_input.additional_data["messages"][-1].tool_calls[0].id,
        )
    )

    # Step 32: Request chart rendering through tool call
    step_input.additional_data["messages"].append(
        AssistantMessage(
            role="assistant",
            tool_calls=[
                {
                    "id": str(uuid.uuid4()),
                    "type": "function",
                    "function": {
                        "name": "render_standard_charts_and_table",  # Frontend rendering function
                        "arguments": json.dumps(
                            {"investment_summary": step_input.additional_data["investment_summary"]}
                        ),
                    },
                }
            ],
            id=str(uuid.uuid4()),
        )
    )
    
    # Step 33: Mark allocation calculation as completed
    index = len(step_input.additional_data["tool_logs"]) - 1
    step_input.additional_data["emit_event"](
        StateDeltaEvent(
            type=EventType.STATE_DELTA,
            delta=[
                {
                    "op": "replace",
                    "path": f"/tool_logs/{index}/status",
                    "value": "completed",
                }
            ],
        )
    )
    await asyncio.sleep(0)  # Yield control to event loop
    return


# WORKFLOW STEP 4: Generate market insights and analysis
# This function creates bull/bear insights for the analyzed stocks
async def gather_insights(step_input):
    # Step 1: Check if we have tool calls to process from previous steps
    if step_input.additional_data["messages"][-1].tool_calls is None:
        return StepOutput(
            content=step_input.additional_data
        )
    
    # Step 2: Initialize tool logging for insights generation
    tool_log_id = str(uuid.uuid4())
    step_input.additional_data["tool_logs"].append(
        {
            "id": tool_log_id,
            "message": "Extracting Key insights",
            "status": "processing",
        }
    )
    
    # Step 3: Emit UI update for insights extraction status
    step_input.additional_data["emit_event"](
        StateDeltaEvent(
            type=EventType.STATE_DELTA,
            delta=[
                {
                    "op": "add",
                    "path": "/tool_logs/-",
                    "value": {
                        "message": "Extracting Key insights",
                        "status": "processing",
                        "id": tool_log_id,
                    },
                }
            ],
        )
    )
    await asyncio.sleep(0)  # Yield control to event loop
    
    # Step 4: Extract ticker symbols for insight generation
    tickers = step_input.additional_data["be_arguments"]['ticker_symbols']
    
    # Step 5: Initialize OpenAI client for insights generation
    model = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Step 6: Request insights generation from AI
    # Use specialized insights prompt and generate_insights tool
    response = model.chat.completions.create(
        model="gpt-4.1-mini",  # Use GPT-4 mini model
        messages=[
            {"role": "system", "content": insights_prompt},  # Insights generation prompt
            {"role": "user", "content": json.dumps(tickers)},  # Ticker symbols as input
        ],
        tools=[generate_insights],  # Tool for generating bull/bear insights
    )
    
    # Step 7: Process insights response and merge with existing data
    if response.choices[0].finish_reason == "tool_calls":
        # Step 8: Extract existing arguments from previous tool call
        args_dict = json.loads(step_input.additional_data["messages"][-1].tool_calls[0].function.arguments)

        # Step 9: Add the insights key to existing arguments
        # Add the insights key
        args_dict["insights"] = json.loads(
            response.choices[0].message.tool_calls[0].function.arguments
        )

        # Step 10: Update the tool call with merged data (charts + insights)
        # Convert back to string
        step_input.additional_data["messages"][-1].tool_calls[0].function.arguments = json.dumps(args_dict)
    else:
        # Step 11: Handle case where insights generation failed
        step_input.additional_data["insights"] = {}  # Empty insights
    
    # Step 12: Mark insights extraction as completed
    index = len(step_input.additional_data["tool_logs"]) - 1
    step_input.additional_data["emit_event"](
        StateDeltaEvent(
            type=EventType.STATE_DELTA,
            delta=[
                {
                    "op": "replace",
                    "path": f"/tool_logs/{index}/status",
                    "value": "completed",
                }
            ],
        )
    )
    await asyncio.sleep(0)  # Yield control to event loop
    
    # Step 13: Return final workflow output
    return StepOutput(
        content=step_input.additional_data
    )
    

# WORKFLOW DEFINITION: Complete stock analysis pipeline
# This workflow orchestrates all the steps in sequence:
# 1. chat: Parse user input and extract parameters
# 2. simultion: Gather historical stock data
# 3. cash_allocation: Calculate portfolio performance and allocations
# 4. gather_insights: Generate market insights
stock_analysis_workflow = Workflow(
    name="Mixed Execution Pipeline",
    steps=[chat, simultion, cash_allocation, gather_insights],  # Function
)


# UTILITY FUNCTION: Convert OpenAI tool call format
# Converts OpenAI tool call objects to our internal format
def convert_tool_call(tc):
    return {
        "id": tc.id,  # Unique identifier for the tool call
        "type": "function",  # Type of tool call (always "function")
        "function": {
            "name": tc.function.name,  # Function name to call
            "arguments": tc.function.arguments,  # JSON string of arguments
        },
    }
