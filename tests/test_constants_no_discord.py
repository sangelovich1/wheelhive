# tests/test_constants_no_discord.py
import ast, pathlib

CONST = pathlib.Path(__file__).parent.parent / "src" / "constants.py"

def test_constants_does_not_import_discord():
    tree = ast.parse(CONST.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "discord" not in imported, "constants.py must not import discord"

def test_constants_guild_values():
    import sys
    sys.path.insert(0, str(CONST.parent))
    import constants
    assert constants.GUILDS == [1349592236375019520]
    assert constants.DEV_GUILDS == [1349592236375019520]
    assert constants.ALLOWED_GUILD_IDS == {1349592236375019520}
