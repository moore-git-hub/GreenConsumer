import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONTRACT_HEAD = "36bfd0f2d571570c914c13cb70403b0aa9fc33b1"


class Harness:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def check(self, label, condition, detail=None):
        if condition:
            self.passed += 1
            print(f"PASS {label}")
            return
        self.failed += 1
        print(f"FAIL {label}: {detail!r}")


def _literal_assignment(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


def _words(text):
    return re.findall(r"[A-Za-z0-9']+", text)


def _git_blob(path):
    proc = subprocess.run(
        ["git", "show", f"{CONTRACT_HEAD}:{path}"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return proc.stdout


def main():
    h = Harness()
    timeline = _literal_assignment("simulation_core.py", "ENTERPRISE_STRATEGY")
    templates = _literal_assignment("clarification_injector.py", "CONTENT_TEMPLATES")

    tick5 = timeline[5]
    rational = templates["rational-evidence"]
    empathy = templates["emotional-empathy"]
    both_templates = rational + "\n" + empathy

    banned_authorized = [
        "Oatly",
        "Blackstone",
        "Trump",
        "Stephen Schwarzman",
        "SEC",
        "Rainforest Alliance",
        "Bureau Veritas",
        "Spruce Point",
        "Twitter",
        "OTLY",
        "Nasdaq",
    ]
    h.check(
        "fictional brand marker",
        "VerdantCo is a fictional sustainability-oriented consumer brand created solely for this experiment."
        in tick5,
    )
    h.check("no Oatly in authorized Tick5", "Oatly" not in tick5)
    h.check("no Blackstone in authorized Tick5", "Blackstone" not in tick5)
    h.check("no real person in authorized Tick5", all(x not in tick5 for x in ["Trump", "Stephen Schwarzman"]))
    h.check(
        "no real institution in clarification templates",
        all(x not in both_templates for x in banned_authorized),
        [x for x in banned_authorized if x in both_templates],
    )
    h.check("authorized Tick5 is fictional", "fictional" in tick5.lower() and "hypothetical" in tick5.lower())

    shared_facts = [
        "minority stake",
        "no board control over VerdantCo's sustainability policy",
        "prior communication about the partnership was insufficient",
        "publish partnership governance information",
        "publish an independent sustainability review",
        "future-investment review safeguard",
        "trust must be rebuilt through observable actions",
    ]
    for fact in shared_facts:
        h.check(f"shared fact rational {fact}", fact in rational)
        h.check(f"shared fact empathy {fact}", fact in empathy)
    h.check("shared factual backbone", all(f in rational and f in empathy for f in shared_facts))
    h.check("shared commitments", rational.count("we will") == empathy.count("we will"), (rational.count("we will"), empathy.count("we will")))

    rational_words = len(_words(rational))
    empathy_words = len(_words(empathy))
    diff_rate = abs(rational_words - empathy_words) / max(rational_words, empathy_words)
    h.check("word-count difference <=10%", diff_rate <= 0.10, (rational_words, empathy_words, diff_rate))
    h.check("major fact item counts equal", rational.count("Fact ") == 7 and empathy.count("Fact ") == 7)
    h.check("commitment counts equal", rational.count("we will") == empathy.count("we will"))
    h.check(
        "hypothetical markers in both",
        all("Hypothetical experimental stimulus" in x and "Fictional scenario" in x for x in [rational, empathy]),
    )

    rational_markers = [
        "structured explanation",
        "document disclosure",
        "checkable evidence",
        "verification",
        "audit",
        "procedural transparency",
        "facts consumers can inspect",
    ]
    empathy_markers = [
        "responsibility",
        "consumer frustration",
        "value identification",
        "relationship repair",
        "community concern",
        "frustration and concern",
    ]
    h.check("rational framing markers present", all(x in rational for x in rational_markers))
    h.check("empathy framing markers present", all(x in empathy for x in empathy_markers))

    from experiment_config import (
        CONTENT_LEVELS,
        EXPERIMENT_MATRIX_VERSION,
        generate_experiment_matrix,
    )

    h.check("content factors unchanged", tuple(CONTENT_LEVELS) == ("rational-evidence", "emotional-empathy"))
    matrix = generate_experiment_matrix()
    immediate = {c.clarification_tick for c in matrix if c.timing_factor == "immediate"}
    delayed = {c.clarification_tick for c in matrix if c.timing_factor == "delayed"}
    h.check("matrix version unchanged", EXPERIMENT_MATRIX_VERSION == "3.0")
    h.check("clarification timing unchanged", immediate == {6} and delayed == {10}, (immediate, delayed))

    protected = [
        "mechanism_v2.py",
        "plugins/agent/reflect/GreenCognitionPlugin.py",
        "plugins/agent/plan/ConsumerPlanPlugin.py",
        "node_selector.py",
        "plugins/environment/network/SocialNetworkPlugin.py",
        "experiment_config.py",
    ]
    for path in protected:
        current = (ROOT / path).read_text(encoding="utf-8")
        h.check(f"protected source unchanged {path}", current == _git_blob(path))
    h.check("mechanism equations unchanged", (ROOT / "mechanism_v2.py").read_text(encoding="utf-8") == _git_blob("mechanism_v2.py"))
    h.check("channel logic unchanged", (ROOT / "node_selector.py").read_text(encoding="utf-8") == _git_blob("node_selector.py"))
    h.check("network unchanged", (ROOT / "plugins/environment/network/SocialNetworkPlugin.py").read_text(encoding="utf-8") == _git_blob("plugins/environment/network/SocialNetworkPlugin.py"))
    h.check("RNG unchanged", (ROOT / "experiment_config.py").read_text(encoding="utf-8") == _git_blob("experiment_config.py"))

    print(f"RATIONAL_WORD_COUNT: {rational_words}")
    print(f"EMPATHY_WORD_COUNT: {empathy_words}")
    print(f"WORD_COUNT_DIFFERENCE_RATE: {diff_rate:.6f}")
    print(f"Passed: {h.passed}")
    print(f"Failed: {h.failed}")
    raise SystemExit(1 if h.failed else 0)


if __name__ == "__main__":
    main()
