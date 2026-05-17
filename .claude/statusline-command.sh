#!/usr/bin/env bash
# Claude Code status line — two-line multiline layout
# Reads JSON from stdin and outputs two lines

input=$(cat)

# --- Extract fields ---
cwd=$(echo "$input" | jq -r '.cwd // .workspace.current_dir // ""')
model=$(echo "$input" | jq -r '.model.display_name // ""')
session_name=$(echo "$input" | jq -r '.session_name // empty')
vim_mode=$(echo "$input" | jq -r '.vim.mode // empty')
effort=$(echo "$input" | jq -r '.effort.level // empty')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
remaining_pct=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')
input_tokens=$(echo "$input" | jq -r '.context_window.current_usage.input_tokens // empty')
output_tokens=$(echo "$input" | jq -r '.context_window.current_usage.output_tokens // empty')
window_size=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
five_hour=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
seven_day=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

# --- Git branch (skip lock to avoid interfering with running operations) ---
git_branch=""
if [ -n "$cwd" ] && cd "$cwd" 2>/dev/null; then
  git_branch=$(GIT_OPTIONAL_LOCKS=0 git symbolic-ref --short HEAD 2>/dev/null || GIT_OPTIONAL_LOCKS=0 git rev-parse --short HEAD 2>/dev/null)
fi

# --- ANSI colors (dimmed-friendly) ---
RESET='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
CYAN='\033[36m'
YELLOW='\033[33m'
GREEN='\033[32m'
MAGENTA='\033[35m'
WHITE='\033[37m'
BLUE='\033[34m'
RED='\033[31m'

SEP="$(printf "${DIM} · ${RESET}")"

# ============================================================
# LINE 1: dir · git branch · model · effort · vim · session
# ============================================================
line1=""

# Working directory (shorten home to ~)
if [ -n "$cwd" ]; then
  home_dir="$HOME"
  display_dir="${cwd/#$home_dir/\~}"
  line1="${line1}$(printf "${BOLD}${CYAN}%s${RESET}" "$display_dir")"
fi

# Git branch
if [ -n "$git_branch" ]; then
  line1="${line1}$(printf " ${DIM}on${RESET} ${MAGENTA}%s${RESET}" "$git_branch")"
fi

# Model
if [ -n "$model" ]; then
  line1="${line1}${SEP}$(printf "${YELLOW}%s${RESET}" "$model")"
fi

# Effort level
if [ -n "$effort" ]; then
  line1="${line1}${SEP}$(printf "${DIM}effort:${RESET} ${WHITE}%s${RESET}" "$effort")"
fi

# Vim mode
if [ -n "$vim_mode" ]; then
  line1="${line1}${SEP}$(printf "${BOLD}${GREEN}%s${RESET}" "$vim_mode")"
fi

# Session name
if [ -n "$session_name" ]; then
  line1="${line1}${SEP}$(printf "${DIM}%s${RESET}" "$session_name")"
fi

# ============================================================
# LINE 2: context bar + token usage + rate limits
# ============================================================
line2=""

if [ -n "$used_pct" ]; then
  # Build a 20-char progress bar with sub-cell partial-block rendering
  bar_width=20
  # partial_blocks[0] is unused; 1..7 map to one-eighth increments
  partial_blocks=("" "▏" "▎" "▍" "▌" "▋" "▊" "▉")
  total_eighths=$(echo "$used_pct $bar_width" | awk '{printf "%d", ($1/100)*$2*8 + 0.5}')
  full_cells=$(( total_eighths / 8 ))
  partial_idx=$(( total_eighths % 8 ))
  # Clamp full_cells to bar_width
  if [ "$full_cells" -gt "$bar_width" ]; then full_cells=$bar_width; partial_idx=0; fi
  # Count of empty cells (partial block, if any, occupies one cell)
  has_partial=0
  [ "$partial_idx" -gt 0 ] && [ "$full_cells" -lt "$bar_width" ] && has_partial=1
  empty_cells=$(( bar_width - full_cells - has_partial ))

  bar_filled=""
  bar_partial=""
  bar_empty=""
  for i in $(seq 1 "$full_cells");  do bar_filled="${bar_filled}█"; done
  [ "$has_partial" -eq 1 ] && bar_partial="${partial_blocks[$partial_idx]}"
  for i in $(seq 1 "$empty_cells"); do bar_empty="${bar_empty}░";  done

  # Pick bar color based on usage (green → yellow → red as usage climbs)
  if [ "$(echo "$used_pct >= 15" | bc 2>/dev/null)" = "1" ]; then
    bar_color="$RED"
  elif [ "$(echo "$used_pct >= 10" | bc 2>/dev/null)" = "1" ]; then
    bar_color="$YELLOW"
  else
    bar_color="$GREEN"
  fi

  used_int=$(printf "%.0f" "$used_pct")
  remaining_int=""
  if [ -n "$remaining_pct" ]; then
    remaining_int=$(printf "%.0f" "$remaining_pct")
  fi

  line2="${line2}$(printf "${DIM}[${RESET}${bar_color}%s%s${RESET}${DIM}%s]${RESET}" "$bar_filled" "$bar_partial" "$bar_empty")"
  line2="${line2}$(printf " ${DIM}context:${RESET} ${WHITE}%s%%${RESET}${DIM} used${RESET}" "$used_int")"
  if [ -n "$remaining_int" ]; then
    line2="${line2}$(printf "${DIM} · ${RESET}${WHITE}%s%%${RESET}${DIM} remaining${RESET}" "$remaining_int")"
  fi

  # Token counts (in/out) if available
  if [ -n "$input_tokens" ] && [ -n "$output_tokens" ]; then
    in_k=$(echo "$input_tokens" | awk '{printf "%.1fk", $1/1000}')
    out_k=$(echo "$output_tokens" | awk '{printf "%.1fk", $1/1000}')
    line2="${line2}$(printf "${DIM} · in:${RESET}${WHITE}%s${RESET}${DIM} out:${RESET}${WHITE}%s${RESET}" "$in_k" "$out_k")"
  fi
fi

# Rate limits (5h / 7d) when available
rate_part=""
if [ -n "$five_hour" ]; then
  five_int=$(printf "%.0f" "$five_hour")
  rate_part="${rate_part}$(printf "${DIM}5h:${RESET}${WHITE}%s%%${RESET}" "$five_int")"
fi
if [ -n "$seven_day" ]; then
  seven_int=$(printf "%.0f" "$seven_day")
  [ -n "$rate_part" ] && rate_part="${rate_part}$(printf "${DIM} · ${RESET}")"
  rate_part="${rate_part}$(printf "${DIM}7d:${RESET}${WHITE}%s%%${RESET}" "$seven_int")"
fi
if [ -n "$rate_part" ]; then
  if [ -n "$line2" ]; then
    line2="${line2}${SEP}${rate_part}"
  else
    line2="${rate_part}"
  fi
fi

# --- Output both lines ---
printf "%b\n%b" "$line1" "$line2"
