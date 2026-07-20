import argparse
from collections.abc import Generator

# Tuple format: (start_frame, end_frame_exclusive_or_none, step)
# None is used for the exclusive end when defining a single frame index.
FrameRangeTuple = tuple[int, int | None, int | tuple[str, int]]


def _parse_single_range_string(range_str: str) -> FrameRangeTuple:
    """
    INTERNAL HELPER: Parses a single range string using only the Python slice
    notation (e.g., '1:100:4', ':50', '20:', '::-1', '::COUNT=2').
    """
    default_step = 1

    # convert COUNT=2 to parsable ::COUNT=2
    range_str = f"::{range_str}" if range_str.startswith("COUNT=") else range_str

    try:
        if ":" not in range_str:
            msg = "Slice format requires the ':' range separator for range tokens."
            raise ValueError(msg)

        parts = [p.strip() for p in range_str.split(":")]

        if len(parts) < 2 or len(parts) > 3:
            msg = "Slice format requires one or two ':' separators."
            raise ValueError(msg)

        # START
        start_str = parts[0]
        start = int(start_str) if start_str else 0

        # END
        end_str = parts[1]
        # Use -1 as placeholder for "until the end"
        end: int | None = int(end_str) if end_str else -1

        # STEP
        step_str = parts[2] if len(parts) == 3 else ""
        if step_str.upper().startswith("COUNT="):
            count = int(step_str.replace("COUNT=", ""))
            if count < 0:
                msg = "COUNT must be a positive integer."
                raise argparse.ArgumentTypeError(msg)
            step = ("COUNT", count)
        else:
            step = int(step_str) if step_str else default_step
            if step <= 0:
                msg = "Step value must be a positive integer"
                raise argparse.ArgumentTypeError(msg)

    except ValueError as e:
        msg = f"Invalid range format '{range_str}'. Use START:END:STEP (e.g., 1:100:4). Error: {e}"
        raise argparse.ArgumentTypeError(msg) from e
    return (start, end, step)


class FlexiRange:
    """
    Holds the raw list of frame selection instructions, allowing delayed
    resolution of negative indices until the total sequence length is known.
    """

    def __init__(self, instructions: list[FrameRangeTuple] = None):
        if instructions is None:
            self.instructions = [(0, -1, 1)]
        else:
            self.instructions = instructions

    def __str__(self) -> str:
        return " ".join([f"{i}" for i in self.instructions])

    def resolve_indices(self, sequence_length: int) -> Generator[int, None, None]:
        """
        Takes the parsed frame selection instructions and yields the actual frame indices,
        resolving negative indices and ensuring deduplication.
        """
        if sequence_length <= 0:
            return

        yielded_indices: set[int] = set()

        for start, end, step in self.instructions:
            # if the start is a negative number, we treat is as relative to the sequence length
            if start < 0:
                start += sequence_length
            # Clip to within valid bounds [0, sequence_length-1]
            start = max(0, min(sequence_length - 1, start))

            # single index instruction
            if end is None:
                # We simply yield the resolved start if it's within bounds.
                index = start
                if index not in yielded_indices:
                    yield index
                    yielded_indices.add(index)
                continue

            # Resolve inclusive end index
            if end < 0:
                end = sequence_length + end
            # Clip resolved indices to be within the valid bounds [0, sequence_length-1]
            end = max(0, min(sequence_length - 1, end))

            if isinstance(step, int):
                # Generate indices for this range instruction
                current_range = range(start, end + 1, step)
                for index in current_range:
                    if index not in yielded_indices:
                        yield index
                        yielded_indices.add(index)

            elif isinstance(step, tuple) and step[0] == "COUNT":
                cnt = step[1]
                span = abs(end - start)
                indices_to_yield = []

                if cnt == 1:
                    # User Request: middle frame
                    index = start + round(span / 2)
                    indices_to_yield.append(index)

                elif cnt == 2:
                    # User Request: first and last frame
                    indices_to_yield.append(start)
                    indices_to_yield.append(end)

                elif cnt >= 3:
                    # User Request: first, last, and N-2 evenly spaced frames (standard linspace)
                    for i in range(cnt):
                        # Interpolation formula: Start + round( (i / (N-1)) * Span ) for i in [0, N-1]
                        # Ensures the first point (i=0) is 'final_start' and the last (i=cnt-1) is 'final_inclusive_end'
                        index = start + round((i / (cnt - 1)) * span)
                        indices_to_yield.append(index)

                for index in indices_to_yield:
                    # Deduplicate and ensure index is within sequence length (though it should be safe)
                    if 0 <= index < sequence_length and index not in yielded_indices:
                        yield index
                        yielded_indices.add(index)

                continue  # Skip to the next instruction


FLEXI_RANGE_FULL = FlexiRange()


def _create_flexi_range_from_tokens(tokens: list[str]) -> FlexiRange:
    """
    Parses a list of tokens into a single FlexiRange object.
    """
    if not tokens:
        return FlexiRange()

    instructions: list[FrameRangeTuple] = []

    for token in tokens:  # example tokens: 1 -1 1:4 :4 ::10 10:20:2 ::COUNT=10 COUNT=3
        try:
            is_range_syntax = ":" in token or "COUNT=" in token

            if is_range_syntax:
                instructions.append(_parse_single_range_string(token))
            else:
                frame_id = int(token)
                # Convert single ID into a one-frame instruction using None as the end marker
                instructions.append((frame_id, None, 1))

        except ValueError as e:  # noqa: PERF203
            msg = f"Token '{token}' is neither a valid range nor a valid integer frame ID."
            raise argparse.ArgumentTypeError(msg) from e

    return FlexiRange(instructions)


def add_flexi_range_argument(
    parser: argparse.ArgumentParser,
    description: str,
    name: str,
    short_name: str | None = None,  # short_name is optional
    *,
    default: str = "ALL",
    required: bool = False,
) -> argparse.ArgumentParser:
    """
    Adds a flexible frame selection argument (--frame or -f) to the parser.
    The argument accepts individual indices and Python slice notation.
    """

    arg_names: list[str] = [name]
    if short_name is not None:
        arg_names.append(short_name)

    help_text = (
        f"{description} "
        "Specify individually (e.g. 0 7 -5 -1) or via python slice (e.g 5:10 15: 10:50:10). "
        "Slice notation (START:INCLUSIVE_END:STEP). "
        f"Or request evenly spaced samples: e.g. {name} ::COUNT=3. "
        f"To request no samples at all use ::COUNT=0. "
        f"You can mix the styles: e.g. {name} 0:10 15 -1. "
    )

    if default == "ALL":
        default = FlexiRange()
        help_text += "Default: 0:-1:1 - all"

    parser.add_argument(
        *arg_names,  # Unpack the list of names
        action=CreateFlexiRange,
        help=help_text,
        default=default,
        required=required,
    )
    return parser


class CreateFlexiRange(argparse.Action):
    """
    Custom argparse Action used to handle multiple tokens (nargs='+')
    and consolidate them into a single FlexiRange object.
    """

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs="*", **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        flexi_range_object = _create_flexi_range_from_tokens(values)
        setattr(namespace, self.dest, flexi_range_object)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Flexi range test")
    add_flexi_range_argument(parser, "Select frames for download.", "--frame", "-f")
    # parser.add_argument("--frame", "-f", action=CreateFlexiRange, default=FlexiRange())  # noqa: ERA001
    args = parser.parse_args()
    selection: FlexiRange = args.frame

    total_length = 100
    for frame_index in selection.resolve_indices(total_length):
        print(frame_index)
