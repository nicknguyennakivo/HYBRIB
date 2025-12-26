# parser/testcase_parser.py

from parser.dsl_models import TestCase, Step

def parse_testcase(text: str) -> TestCase:
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    name = None
    depends_on = []
    pre, run, finally_ = [], [], []
    # continue implementing parsing two parameters
    max_wait = 60  # default 60 minutes
    poll_interval = 3  # default 3 minutes

    section = None

    for line in lines:
        if line.startswith("@testcase"):
            name = line.split()[1]

        elif line.startswith("@depends_on"):
            depends_on = line.split()[1:]

        elif line.startswith("@max_wait"):
            try:
                max_wait = int(line.split()[1])
            except Exception:
                pass

        elif line.startswith("@poll_interval"):
            try:
                poll_interval = int(line.split()[1])
            except Exception:
                pass

        elif line == "@pre":
            section = "pre"

        elif line == "@run":
            section = "run"

        elif line == "@finally":
            section = "finally"

        else:
            step = Step(
                text=line,
                is_physical=line.startswith("[physical]")
            )

            if section == "pre":
                pre.append(step)
            elif section == "run":
                run.append(step)
            elif section == "finally":
                finally_.append(step)

    return TestCase(
        name=name,
        depends_on=depends_on,
        pre=pre,
        run=run,
        finally_=finally_,
        max_wait=max_wait,
        poll_interval=poll_interval,
    )
