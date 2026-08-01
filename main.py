from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED

console = Console()

def create_header() -> Text:
    """Builds the top bar navigation."""
    header = Text()
    header.append("scrut", style="bold white")
    header.append(" ✨ ", style="#FBBF24")
    header.append("repo / ", style="#52525B")
    header.append("frontend-api / ", style="white")
    header.append("main ", style="#52525B")
    header.append("(1.4s, 118 functions total)", style="#71717A")
    return header

def create_needs_review_content() -> Text:
    """Builds the left-side 'Needs Review' output."""
    content = Text()

    # Section Header
    content.append("[Needs Review]", style="bold #FBBF24")
    content.append(" ⚠️\n", style="#FBBF24")

    # Item 1: LoginHandler
    content.append("  C LoginHandler ", style="bold white")
    content.append("........................... ", style="#3F3F46")
    content.append("(2) f\n", style="#71717A")
    
    content.append("    f authenticate ", style="white")
    content.append("........ ", style="#3F3F46")
    content.append("(p:4 n:3 l:84)\n", style="#71717A")
    
    content.append("    f _validate_session ", style="white")
    content.append("..... ", style="#3F3F46")
    content.append("(p:2 n:1 l:15)\n", style="#71717A")
    
    content.append("    f get_current_user ", style="white")
    content.append("...... ", style="#3F3F46")
    content.append("(p:1 n:1 l:22)\n\n", style="#71717A")

    # Item 2: models.py
    content.append("[src/users/models.py]", style="bold #38BDF8")
    content.append(" ⚠️\n", style="#FBBF24")
    content.append("  C UserProfile ", style="bold white")
    content.append("........................... ", style="#3F3F46")
    content.append("(1) f\n", style="#71717A")
    content.append("    w Unused parameter 'timezone' (line 45)\n\n", style="#FBBF24")

    # Item 3: helpers.py
    content.append("[src/utils/helpers.py]", style="bold #38BDF8")
    content.append(" ⚠️\n", style="#FBBF24")
    content.append("  f format_date ", style="bold white")
    content.append("........... ", style="#3F3F46")
    content.append("(p:2 n:3 l:140)\n", style="#71717A")
    content.append("    w Unused parameter 'timezone'\n", style="#FBBF24")
    content.append("    w Function length exceeds threshold (140/100)\n\n", style="#FBBF24")

    # Item 4: views.py
    content.append("[src/billing/views.py]", style="bold #38BDF8")
    content.append(" 🛑\n", style="#EF4444")
    content.append("  C CheckoutView ", style="bold white")
    content.append("........................... ", style="#3F3F46")
    content.append("(4) f\n", style="#71717A")
    content.append("    E Parameter 'payment_token' is required, missing type annotation\n", style="#EF4444")
    content.append("    f apply_discount ", style="white")
    content.append("....... ", style="#3F3F46")
    content.append("(p:3 n:3 l:55)\n", style="#71717A")
    content.append("    w Function length exceeds threshold (55/50)", style="#FBBF24")

    return content

def create_passing_content() -> Text:
    """Builds the right-side 'Passing' output."""
    content = Text()

    content.append("[Passing]", style="bold #10B981")
    content.append(" ✨\n\n", style="#FBBF24")

    passing_files = [
        "auth.py",
        "config.py",
        "models.py",
        "parser.py",
        "test_auth.py",
        "test_helpers.py",
        "test_models.py",
        "test_views.py",
    ]

    for file_name in passing_files:
        content.append("✓ ", style="bold #10B981")
        content.append(f"{file_name}\n", style="#A1A1AA")

    content.append("✓ ", style="bold #10B981")
    content.append("[+14 additional files all good]", style="#52525B")

    return content

def render_ui():
    """Combines left and right panels into a single bordered box using a Rich Table."""
    console.clear()

    # Render Header
    console.print(create_header())
    console.print()  # Empty line spacing

    # Create a borderless table layout to hold left & right columns side-by-side
    grid = Table.grid(expand=True)
    grid.add_column(ratio=7)
    grid.add_column(ratio=3)

    # Put content in table columns
    grid.add_row(
        create_needs_review_content(),
        create_passing_content()
    )

    # Wrap the grid into a single outer panel with vertical divider border effect
    # We use rich's grid vertical border styling via Table
    bordered_table = Table(
        box=ROUNDED,
        show_header=False,
        show_edge=True,
        border_style="#3F3F46",
        expand=True,
        pad_edge=True
    )
    
    bordered_table.add_column(ratio=7)
    bordered_table.add_column(ratio=3, border_style="#3F3F46")

    bordered_table.add_row(
        create_needs_review_content(),
        create_passing_content()
    )

    console.print(bordered_table)

if __name__ == "__main__":
    render_ui()