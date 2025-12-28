import re

def is_valid_stock_code(stock_code):
    """
    Validate stock code format: digits followed by .SH or .SZ

    Examples:
        - 601059.SH (valid)
        - 002549.SZ (valid)
        - 000001 (invalid, missing suffix)
        - 601059.sh (invalid, lowercase)
        - 123.SH (invalid, not 6 digits)

    Args:
        stock_code (str): The stock code to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if not stock_code or not isinstance(stock_code, str):
        return False

    # Pattern: 6 digits followed by .SH or .SZ
    pattern = r'^\d{6}\.(SH|SZ)$'
    return bool(re.match(pattern, stock_code.strip()))

def format_stock_code(stock_code):
    """
    Format stock code to standard format (uppercase suffix)

    Args:
        stock_code (str): The stock code to format

    Returns:
        str: Formatted stock code, or original if invalid
    """
    if not stock_code:
        return stock_code

    stock_code = stock_code.strip().upper()
    if is_valid_stock_code(stock_code):
        return stock_code
    return stock_code

def get_stock_market(stock_code):
    """
    Get the stock market from stock code

    Args:
        stock_code (str): The stock code

    Returns:
        str: 'SH' for Shanghai, 'SZ' for Shenzhen, None if invalid
    """
    if is_valid_stock_code(stock_code):
        return stock_code.split('.')[-1]
    return None
