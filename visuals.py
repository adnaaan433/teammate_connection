import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from mplsoccer import VerticalPitch
import numpy as np
from adjustText import adjust_text


def shorten_name(name):
    """Convert 'Lamine Yamal' → 'L. Yamal', single-word names stay as-is."""
    parts = name.strip().split()
    if len(parts) <= 1:
        return name
    return parts[0][0] + ". " + " ".join(parts[1:])


def _normalise(values, lo, hi):
    """Min-max normalise *values* into [lo, hi]."""
    values = values.astype(float)
    if values.max() == values.min():
        return np.full_like(values, (lo + hi) / 2)
    return lo + (values - values.min()) / (values.max() - values.min()) * (hi - lo)


def plot_combined_network(df_events, player_name, player_known_name=None,
                          name_map=None, team_name="", comp_name="", season_label="", theme="dark"):
    """
    Draw pass network (left) and receiving network (right) on a single figure.

    - Shared title: player display name
    - Shared subtitle: team · season · aggregate stats
    - Per-pitch titles: "Pass Network" / "Receiving Network"
    """

    if name_map is None:
        name_map = {}

    display_name = player_known_name or player_name

    if theme == "light":
        bg_color = "#ffffff"
        pitch_line_color = "#cbd5e1"
        fg_color = "#0f172a"
        muted_color = "#475569"
        title_color = "#d97706"
        node_border = "#e2e8f0"
        arrow_color = "#d97706"
        rank_color = "#64748b"
        passer_color = "#f59e0b"
        receiver_color = "#f59e0b"
        line_base = "#8b5cf6"
        header_color = "#7c3aed"
    else:
        bg_color = "#0e1117"
        pitch_line_color = "#2a3450"
        fg_color = "#e2e8f0"
        muted_color = "#94a3b8"
        title_color = "#fbbf24"
        node_border = "#c4b5fd"
        arrow_color = "#fbbf24"
        rank_color = "#64748b"
        passer_color = "#f59e0b"
        receiver_color = "#f59e0b"
        line_base = "#a78bfa"
        header_color = "#c4b5fd"

    text_path_eff = [
        path_effects.Stroke(linewidth=3, foreground=bg_color),
        path_effects.Normal(),
    ]

    # ── Data prep — pass & receive ────────────────────────────────────────
    df_pass = df_events[df_events["player_name"] == player_name].copy()
    df_recv = df_events[df_events["pass_recipient_name"] == player_name].copy()

    # Aggregate pass network (passer → recipients)
    if not df_pass.empty:
        agg_pass = (
            df_pass.groupby("pass_recipient_name")
            .agg(avg_end_x=("end_x", "mean"), avg_end_y=("end_y", "mean"),
                 pass_count=("end_x", "size"))
            .reset_index()
        )
        agg_pass = agg_pass.nlargest(10, "pass_count").reset_index(drop=True)
        pass_origin_x, pass_origin_y = df_pass["x"].mean(), df_pass["y"].mean()
    else:
        agg_pass = None

    # Aggregate receive network (passers → recipient)
    if not df_recv.empty:
        agg_recv = (
            df_recv.groupby("player_name")
            .agg(avg_x=("x", "mean"), avg_y=("y", "mean"),
                 pass_count=("x", "size"))
            .reset_index()
        )
        agg_recv = agg_recv.nlargest(10, "pass_count").reset_index(drop=True)
        recv_dest_x, recv_dest_y = df_recv["end_x"].mean(), df_recv["end_y"].mean()
    else:
        agg_recv = None

    # ── Create figure with two pitches ────────────────────────────────────
    pitch = VerticalPitch(
        pitch_type="statsbomb",
        pitch_color=bg_color,
        line_color=pitch_line_color,
        linewidth=1.5,
        corner_arcs=True,
    )
    fig, axes = pitch.draw(nrows=1, ncols=2, figsize=(16, 14))
    fig.set_facecolor(bg_color)
    ax_pass, ax_recv = axes[0], axes[1]

    # ─────────────────────────────────────────────────────────────────────
    # LEFT — Pass Network
    # ─────────────────────────────────────────────────────────────────────
    if agg_pass is not None:
        counts_p = agg_pass["pass_count"].values
        lw_p = _normalise(counts_p, 1.0, 10.0)
        alpha_p = _normalise(counts_p, 0.35, 1.0)

        for i, row in agg_pass.iterrows():
            x1, y1 = pass_origin_x, pass_origin_y
            x2, y2 = row["avg_end_x"], row["avg_end_y"]
            pitch.lines(
                x1, y1, x2, y2,
                ax=ax_pass, lw=lw_p[i]+1, color=line_base,
                alpha=float(alpha_p[i]), zorder=2,
            )
            # Midpoint direction arrow
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            dx, dy = x2 - x1, y2 - y1
            length = np.sqrt(dx**2 + dy**2)
            if length > 0:
                eps = 0.5
                ux, uy = dx / length * eps, dy / length * eps
                pitch.annotate(
                    '', xy=(mid_x + ux, mid_y + uy),
                    xytext=(mid_x - ux, mid_y - uy),
                    ax=ax_pass,
                    arrowprops=dict(arrowstyle='->', color=arrow_color,
                                   lw=1.5, mutation_scale=15),
                    zorder=3,
                )

        pitch.scatter(
            agg_pass["avg_end_x"], agg_pass["avg_end_y"],
            s=250, color=line_base, edgecolors=node_border,
            linewidth=1.5, zorder=4, ax=ax_pass,
        )

        texts_pass = []
        for _, row in agg_pass.iterrows():
            recipient_full = row["pass_recipient_name"]
            short = shorten_name(name_map.get(recipient_full, recipient_full))
            ann = pitch.annotate(
                short, xy=(row["avg_end_x"], row["avg_end_y"]),
                ax=ax_pass, fontsize=10, color=fg_color,
                ha="left", va="bottom",
                fontweight="bold",
                path_effects=text_path_eff, zorder=5,
            )
            texts_pass.append(ann)

        adjust_text(texts_pass, ax=ax_pass,
                    force_text=(0.5, 0.5),
                    arrowprops=dict(arrowstyle='-', color=muted_color, lw=0.5))

        # Passer node (orange, larger) — white edge to stand out from lines
        pitch.scatter(
            pass_origin_x, pass_origin_y,
            s=300, color=passer_color, edgecolors=bg_color,
            linewidth=2.5, zorder=6, ax=ax_pass,
        )

    else:
        ax_pass.text(0.5, 0.5, "No pass data", transform=ax_pass.transAxes,
                     ha="center", va="center", fontsize=14, color=muted_color)

    # Per-pitch title
    ax_pass.set_title("Passing Network", color=title_color, fontsize=18,
                      fontweight="bold", fontfamily="sans-serif", pad=0)

    # ─────────────────────────────────────────────────────────────────────
    # RIGHT — Receiving Network
    # ─────────────────────────────────────────────────────────────────────
    if agg_recv is not None:
        counts_r = agg_recv["pass_count"].values
        lw_r = _normalise(counts_r, 1.0, 10.0)
        alpha_r = _normalise(counts_r, 0.35, 1.0)

        for i, row in agg_recv.iterrows():
            x1, y1 = row["avg_x"], row["avg_y"]
            x2, y2 = recv_dest_x, recv_dest_y
            pitch.lines(
                x1, y1, x2, y2,
                ax=ax_recv, lw=lw_r[i]+1, color=line_base,
                alpha=float(alpha_r[i]), zorder=2,
            )
            # Midpoint direction arrow
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            dx, dy = x2 - x1, y2 - y1
            length = np.sqrt(dx**2 + dy**2)
            if length > 0:
                eps = 0.5
                ux, uy = dx / length * eps, dy / length * eps
                pitch.annotate(
                    '', xy=(mid_x + ux, mid_y + uy),
                    xytext=(mid_x - ux, mid_y - uy),
                    ax=ax_recv,
                    arrowprops=dict(arrowstyle='->', color=arrow_color,
                                   lw=1.5, mutation_scale=15),
                    zorder=3,
                )

        pitch.scatter(
            agg_recv["avg_x"], agg_recv["avg_y"],
            s=250, color=line_base, edgecolors=node_border,
            linewidth=1.5, zorder=4, ax=ax_recv,
        )

        texts_recv = []
        for _, row in agg_recv.iterrows():
            passer_full = row["player_name"]
            short = shorten_name(name_map.get(passer_full, passer_full))
            ann = pitch.annotate(
                short, xy=(row["avg_x"], row["avg_y"]),
                ax=ax_recv, fontsize=10, color=fg_color,
                ha="left", va="bottom",
                fontweight="bold",
                path_effects=text_path_eff, zorder=5,
            )
            texts_recv.append(ann)

        adjust_text(texts_recv, ax=ax_recv,
                    force_text=(0.5, 0.5),
                    arrowprops=dict(arrowstyle='-', color=muted_color, lw=0.5))

        # Receiver node (orange, larger) — background edge to stand out from lines
        pitch.scatter(
            recv_dest_x, recv_dest_y,
            s=300, color=receiver_color, edgecolors=bg_color,
            linewidth=2.5, zorder=6, ax=ax_recv,
        )

    else:
        ax_recv.text(0.5, 0.5, "No receiving data", transform=ax_recv.transAxes,
                     ha="center", va="center", fontsize=14, color=muted_color)

    # Per-pitch title
    ax_recv.set_title("Receiving Network", color=title_color, fontsize=18,
                      fontweight="bold", fontfamily="sans-serif", pad=0)

    # ─────────────────────────────────────────────────────────────────────
    # STATS TABLES inside each pitch axes (two columns of 5 rows)
    # ─────────────────────────────────────────────────────────────────────
    def _draw_stats_in_axes(ax, agg_df, name_col, accent_color, header=""):
        """Draw a two-column stats table below the pitch, inside the axes."""
        if agg_df is None or agg_df.empty:
            return

        rows = agg_df.sort_values("pass_count", ascending=False).head(10).reset_index(drop=True)
        n = len(rows)
        col1 = rows.iloc[:5]
        col2 = rows.iloc[5:10] if n > 5 else None

        # Header above the stats
        header_y = 0.01
        row_h = 0.025  # vertical spacing in axes fraction

        if header:
            ax.text(0.5, header_y, header, fontsize=12, color=header_color,
                    ha="center", va="center", fontfamily="sans-serif",
                    fontweight="bold", transform=ax.transAxes, clip_on=False)

        for col_idx, chunk in enumerate([col1, col2]):
            if chunk is None:
                continue
            x_rank = 0.06 + col_idx * 0.6
            x_name = 0.075 + col_idx * 0.6
            x_count = 0.35 + col_idx * 0.6

            for j, (_, r) in enumerate(chunk.iterrows()):
                rank = j + 1 + col_idx * 5
                y = -0.025 - j * row_h
                full_name = r[name_col]
                short = shorten_name(name_map.get(full_name, full_name))

                ax.text(x_rank, y, f"{rank}.", fontsize=10, color=rank_color,
                        ha="right", va="center", fontfamily="sans-serif",
                        transform=ax.transAxes, clip_on=False)
                ax.text(x_name, y, short, fontsize=10, color=fg_color,
                        ha="left", va="center", fontfamily="sans-serif",
                        transform=ax.transAxes, clip_on=False)
                ax.text(x_count, y, str(int(r["pass_count"])), fontsize=10,
                        color=accent_color, ha="right", va="center",
                        fontfamily="sans-serif", fontweight="bold",
                        transform=ax.transAxes, clip_on=False)

    _draw_stats_in_axes(ax_pass, agg_pass, "pass_recipient_name", title_color, header="Top 10 Passes To")
    _draw_stats_in_axes(ax_recv, agg_recv, "player_name", title_color, header="Top 10 Receives From")

    # ── Shared title + subtitle ───────────────────────────────────────────
    fig.text(
        0.5, 1.033, f'{display_name}',
        ha="center", va="center",
        fontsize=30, fontweight="bold",
        color=fg_color, fontfamily="sans-serif",
    )

    # Build subtitle — info + credits all in one line
    sub_text = "  ·  ".join(
        p for p in [team_name, comp_name, season_label, "Data: Statsbomb", "Made by: team @adnaaan433 and @Ismailshahid_7"] if p
    )

    fig.text(
        0.5, 1, sub_text,
        ha="center", va="center",
        fontsize=15, color=muted_color,
        fontfamily="sans-serif",
    )

    # ── Viz Explainer Text ───────────────────────────────────────────────
    fig.text(
        0.5, 0, "Nodes: Avg. Locations of Successful Open-Play Passes or Successful Open-Play Passes Receives | Linewidth: Volume of Passes\nOnly Top 10 Passers or Receivers are visualized",
        ha="center", va="center",
        fontsize=10, color=muted_color, fontstyle="italic",
        fontfamily="sans-serif",
    )

    plt.tight_layout(rect=[0, 0.13, 1, 0.93])
    return fig
