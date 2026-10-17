"""
Draws a clean, high-resolution, professional Methodology Pipeline Diagram:
- 5 Horizontal Phases: Testbed -> Telemetry & Detection -> Diagnostic Agent -> Policy & Safety Gate -> Reversible Repair & Audit
- Bottom Adversarial Loop: Controlled Chaos Fault Injection stress-testing the testbed.
- Clean Minimalist Professional Palette (Cobalt Blue, Amber, Teal, Slate, Crimson) matching the presentation theme.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_methodology_pipeline(output_png="methodology_pipeline_model.png"):
    fig, ax = plt.subplots(figsize=(16, 9), dpi=300)
    ax.set_facecolor("#FFFFFF")
    fig.patch.set_facecolor("#FFFFFF")

    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)

    # Color Palette
    C_PRIMARY = "#1D4ED8"       # Cobalt Blue
    C_DARK = "#0F172A"          # Dark Slate
    C_MUTED = "#64748B"         # Slate 500
    C_ACCENT_AMBER = "#D97706"  # Amber
    C_ACCENT_TEAL = "#0D9488"   # Teal
    C_ACCENT_PURPLE = "#7C3AED" # Purple
    C_ACCENT_RED = "#DC2626"    # Crimson for Chaos
    C_ARROW = "#334155"         # Slate 700

    # Main Title & Subtitle Banner
    ax.text(
        50, 97.2, "M.Tech Methodology: Closed-Loop Self-Healing & Resilience Pipeline",
        ha="center", va="center",
        fontsize=16.5, fontweight="bold", color=C_DARK, fontname="DejaVu Sans"
    )
    ax.text(
        50, 93.8, "Systematic Engineering Process: Telemetry Ingestion, Diagnostic Confidence, Policy Governance, Repair, and Chaos Validation",
        ha="center", va="center",
        fontsize=10.2, color="#475569", fontname="DejaVu Sans"
    )

    # 5 Phases Data
    phases = [
        {
            "phase": "PHASE 1: TESTBED",
            "title": "Container Testbed",
            "bg": "#EFF6FF",
            "border": C_PRIMARY,
            "title_col": C_PRIMARY,
            "bullets": [
                ("• Docker Microservices", True),
                ("  (Payments, Auth, API)", False),
                ("• Webhook Ingestion Engine", True),
                ("• Synthetic Traffic Load", True),
                ("• Live HTTP Health Probes", True)
            ]
        },
        {
            "phase": "PHASE 2: TELEMETRY",
            "title": "Telemetry & Detection",
            "bg": "#F8FAFC",
            "border": "#475569",
            "title_col": C_DARK,
            "bullets": [
                ("• Continuous Log Collector", True),
                ("• GitOps Deep Diffing", True),
                ("  (Detects live config drift)", False),
                ("• Z-Score Anomaly Engine", True),
                ("• Global Correlation IDs", True)
            ]
        },
        {
            "phase": "PHASE 3: DIAGNOSIS",
            "title": "Diagnostic Brain",
            "bg": "#FFFBEB",
            "border": C_ACCENT_AMBER,
            "title_col": C_ACCENT_AMBER,
            "bullets": [
                ("• Evidence Aggregation", True),
                ("• Multi-Modal Correlation", True),
                ("• Root Cause Analysis (RCA)", True),
                ("• Calibrated Confidence", True),
                ("  Scale: 0.0 to 1.0 (0-100%)", False)
            ]
        },
        {
            "phase": "PHASE 4: SAFETY GATE",
            "title": "Policy Safety Gate",
            "bg": "#FAF5FF",
            "border": C_ACCENT_PURPLE,
            "title_col": C_ACCENT_PURPLE,
            "bullets": [
                ("• SR-1 to SR-11 Enforcer", True),
                ("• Confidence Gating", True),
                ("  (Conf >= 80% vs HITL)", False),
                ("• Strict Action Allowlist", True),
                ("• Dynamic Circuit Breakers", True)
            ]
        },
        {
            "phase": "PHASE 5: REPAIR & AUDIT",
            "title": "Repair & Audit",
            "bg": "#F0FDF4",
            "border": C_ACCENT_TEAL,
            "title_col": C_ACCENT_TEAL,
            "bullets": [
                ("• Pre-Repair Checkpoint", True),
                ("• Reversible Rollback", True),
                ("• GitOps Config Patch", True),
                ("• Post-Repair Health Probe", True),
                ("• SHA-256 Chained Ledger", True)
            ]
        }
    ]

    card_w = 16.4
    card_h = 39.5
    start_x = 3.5
    gap_x = 3.7
    card_y = 44.0

    for idx, p_info in enumerate(phases):
        cx = start_x + idx * (card_w + gap_x)

        # Phase Badge Header Pill
        pill = patches.FancyBboxPatch(
            (cx, card_y + card_h + 1.2), card_w, 4.0,
            boxstyle="round,pad=0.5,rounding_size=1.2",
            facecolor=p_info["border"],
            edgecolor=p_info["border"],
            linewidth=1.0,
            zorder=3
        )
        ax.add_patch(pill)
        ax.text(
            cx + card_w / 2, card_y + card_h + 3.2, p_info["phase"],
            ha="center", va="center",
            fontsize=9.0, fontweight="bold", color="#FFFFFF",
            fontname="DejaVu Sans", zorder=4
        )

        # Main Phase Card
        card = patches.FancyBboxPatch(
            (cx, card_y), card_w, card_h,
            boxstyle="round,pad=0.8,rounding_size=2.0",
            facecolor=p_info["bg"],
            edgecolor=p_info["border"],
            linewidth=1.8,
            zorder=2
        )
        ax.add_patch(card)

        # Card Title
        ax.text(
            cx + card_w / 2, card_y + card_h - 3.8, p_info["title"],
            ha="center", va="center",
            fontsize=11.5, fontweight="bold", color=p_info["title_col"],
            fontname="DejaVu Sans", zorder=3
        )

        # Divider inside card
        div_line = patches.Rectangle(
            (cx + 1.5, card_y + card_h - 6.2), card_w - 3.0, 0.25,
            facecolor="#CBD5E1", edgecolor="none", zorder=3
        )
        ax.add_patch(div_line)

        # Bullets Text
        bullet_y = card_y + card_h - 9.8
        for b_text, is_primary in p_info["bullets"]:
            is_sub = not is_primary
            ax.text(
                cx + (2.5 if is_sub else 1.4), bullet_y, b_text,
                ha="left", va="center",
                fontsize=8.6 if is_sub else 9.3,
                fontweight="normal" if is_sub else "bold",
                color="#475569" if is_sub else "#0F172A",
                fontname="DejaVu Sans", zorder=3
            )
            bullet_y -= 4.8

        # Connecting Forward Arrow (Between cards 0->1, 1->2, 2->3, 3->4)
        if idx < 4:
            arrow_start_x = cx + card_w + 0.4
            arrow_end_x = arrow_start_x + gap_x - 0.8
            ax.annotate(
                "", xy=(arrow_end_x, card_y + card_h / 2),
                xytext=(arrow_start_x, card_y + card_h / 2),
                arrowprops=dict(
                    facecolor=C_ARROW, edgecolor=C_ARROW,
                    width=2.2, headwidth=7.5, headlength=7.5
                ),
                zorder=4
            )

    # ==========================================
    # BOTTOM ADVERSARIAL FEEDBACK LOOP: CHAOS
    # ==========================================

    # Feedback Loop Route (From Phase 5 bottom -> down -> left -> up into Phase 1)
    # Right Down Arrow
    p5_cx = start_x + 4 * (card_w + gap_x) + card_w / 2
    p1_cx = start_x + card_w / 2

    # Draw continuous feedback route line
    line_v1 = patches.FancyArrowPatch(
        (p5_cx, card_y), (p5_cx, 26.5),
        arrowstyle="-", color=C_ACCENT_RED, linewidth=2.0, linestyle="--",
        zorder=3
    )
    ax.add_patch(line_v1)

    line_h = patches.FancyArrowPatch(
        (p5_cx, 26.5), (p1_cx, 26.5),
        arrowstyle="-", color=C_ACCENT_RED, linewidth=2.0, linestyle="--",
        zorder=3
    )
    ax.add_patch(line_h)

    line_v2 = patches.FancyArrowPatch(
        (p1_cx, 26.5), (p1_cx, card_y - 0.5),
        arrowstyle="-|>", mutation_scale=16,
        color=C_ACCENT_RED, linewidth=2.0, linestyle="--",
        zorder=4
    )
    ax.add_patch(line_v2)

    # Chaos Injection Central Banner Box
    chaos_box = patches.FancyBboxPatch(
        (22.0, 7.0), 56.0, 23.5,
        boxstyle="round,pad=1.0,rounding_size=2.5",
        facecolor="#FEF2F2",
        edgecolor=C_ACCENT_RED,
        linewidth=2.0,
        zorder=5
    )
    ax.add_patch(chaos_box)

    # Chaos Title Badge
    c_badge = patches.FancyBboxPatch(
        (33.0, 27.2), 34.0, 4.0,
        boxstyle="round,pad=0.5,rounding_size=1.2",
        facecolor=C_ACCENT_RED,
        edgecolor=C_ACCENT_RED,
        linewidth=1.0,
        zorder=6
    )
    ax.add_patch(c_badge)
    ax.text(
        50.0, 29.2, "ADVERSARIAL STRESS-TESTING: CONTROLLED CHAOS INJECTION",
        ha="center", va="center",
        fontsize=9.2, fontweight="bold", color="#FFFFFF",
        fontname="DejaVu Sans", zorder=7
    )

    # Chaos Injection Details (2 Columns inside the chaos box)
    c_col1_x = 25.5
    c_col2_x = 52.5

    chaos_items_col1 = [
        "• SCN-01: Defective Rollout (CrashLoopBackOff)",
        "• SCN-02: Out-of-band Configuration Drift",
    ]
    chaos_items_col2 = [
        "• SCN-03: Post-Deploy Latency & Error Spike",
        "• SCN-04: Ambiguous External Load Spike (HITL)",
    ]

    c_text_y = 22.0
    for item in chaos_items_col1:
        ax.text(
            c_col1_x, c_text_y, item,
            ha="left", va="center",
            fontsize=9.2, fontweight="bold", color="#991B1B",
            fontname="DejaVu Sans", zorder=6
        )
        c_text_y -= 5.0

    c_text_y = 22.0
    for item in chaos_items_col2:
        ax.text(
            c_col2_x, c_text_y, item,
            ha="left", va="center",
            fontsize=9.2, fontweight="bold", color="#991B1B",
            fontname="DejaVu Sans", zorder=6
        )
        c_text_y -= 5.0

    # Safety containment footer note inside chaos box
    ax.text(
        50.0, 10.5,
        "Safety Containment Guarantee: 100% Isolated Container Namespaces  |  Instant Emergency Safety Abort Enabled",
        ha="center", va="center",
        fontsize=8.5, fontweight="bold", color="#7F1D1D",
        fontname="DejaVu Sans", zorder=6
    )

    plt.tight_layout()
    plt.savefig(output_png, bbox_inches="tight", dpi=300)
    plt.close()
    print(f"Methodology diagram successfully generated: {output_png}")

if __name__ == "__main__":
    draw_methodology_pipeline()
