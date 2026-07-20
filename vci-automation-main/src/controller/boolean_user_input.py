def boolean_user_input(
    query_text: str,
    default_choice: bool = True,
    accepted_tokens=["yes", "y"],
    declined_tokens=["no", "n"],
    case_sensitive: bool = False,
    query_suffix: bool = True,
) -> bool:
    """
    Ask the user a yes/no style question and return a boolean value
    based on predefined accepted or declined tokens.

    Parameters:
        query_text (str):
            The prompt to show to the user when requesting input.

        default_choice (bool, optional):
            The fallback value returned when the user's input does not
            match any accepted or declined token, or when the input is empty.
            Defaults to True.

        accepted_tokens (list[str], optional):
            List of strings representing affirmative responses.
            Defaults to ['yes', 'y'].

        declined_tokens (list[str], optional):
            List of strings representing negative responses.
            Defaults to ['no', 'n'].

        case_sensitive (bool, optional):
            If False, both the user input and the token lists are normalized
            to lowercase before comparison. Defaults to False.

        query_suffix (bool, optional):
            If True, the function automatically appends a suffix to the query
            indicating the default choice. The suffix is [Y, n] when the
            default_choice is True and [y, N] when default_choice is False.
            This helps clarify to the user which option is selected by default.
            Defaults to True.

    Returns:
        bool:
            True if the user input matches any accepted token,
            False if it matches any declined token,
            otherwise the value of default_choice.
    """

    if query_suffix:
        query_text = query_text + "[Y, n]" if default_choice else query_text + "[y, N]"

    # Read user input and strip whitespace
    user_input = input(query_text).strip()

    # Normalize input and tokens when case sensitivity is disabled
    if not case_sensitive:
        user_input = user_input.lower()
        accepted_tokens = [t.lower() for t in accepted_tokens]
        declined_tokens = [t.lower() for t in declined_tokens]

    # Determine the result based on matching tokens
    if user_input in accepted_tokens:
        return True
    if user_input in declined_tokens:
        return False
    return default_choice
