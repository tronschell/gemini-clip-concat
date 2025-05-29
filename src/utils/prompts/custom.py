from string import Template

# This is a general-purpose template that can be used for any game.
# To create a custom prompt for a different game:
# 1. Copy this file and name it after your game (e.g., valorant.py)
# 2. Modify the template to match your game's specific needs
# 3. Import the new prompt in src/prompts/__init__.py
# 4. Add the game type to the PROMPT_TEMPLATES dictionary in __init__.py
# 5. Update your config.json to use the new game type

HIGHLIGHT_PROMPT = Template('''
Analyze the provided Counter-Strike 2 gameplay clip to identify highlight moments featuring player `${username}`.
Your analysis **MUST** be confined exclusively to the kill feed region of the video.

**VIDEO REGION OF INTEREST (KILL FEED):**
*   **Resolution Context:** 1440p image
*   **Kill Feed Location:** Top-right of the screen.
*   **Specific Crop Area:** A region of `681px` (width) × `306px` (height) located at coordinates `(1865, 35)` (top-left corner of the region).
*   **CRITICAL INSTRUCTION:** You are to **IGNORE LITERALLY EVERYTHING ELSE** in the video. All information for your analysis (kills, timing, context) must be derived *solely* from what is visible within this specified kill feed region.

**VARIABLES:**
*   **Player of Interest:** `${username}`
*   **Minimum Highlight Duration:** `${min_highlight_duration_seconds}` seconds

**CRITICAL TWO-STEP PROCESS FOR ANALYSIS (Based ONLY on Kill Feed Data):**

**STEP 1: Meticulous Kill Identification (Internal Analysis - For Your Processing)**
Your *absolute first task* is to meticulously scan **ONLY THE SPECIFIED KILL FEED REGION** of the entire video frame-by-frame and create a comprehensive internal list of EVERY single kill made by `${username}`. For each kill, note the following, derived *exclusively* from the kill feed:

1.  **Kill Timestamp (seconds):** The exact second the kill entry appears in the kill feed.
2.  **Victim Name:** The name of the player killed by `${username}`, as shown in the kill feed.
3.  **Weapon Used (Optional, for context):** If identifiable from the weapon icon in the kill feed entry.

**Instructions for Kill Identification (from Kill Feed ONLY):**
*   Prioritize accuracy. Kills by `${username}` are identifiable by their name appearing on the left side of a kill feed entry, often with a distinctive styling (e.g., a thin red outline as previously mentioned, or simply by `${username}` being the agent of the kill). The typical format is: `${username}` [weapon_icon] `victim_name`.
*   Conversely, if `${username}` is the `victim_name` (appears on the right side of a kill feed entry), this is a death for `${username}` and should be noted internally but **NOT** used to initiate a highlight.
*   You are processing the video at 1 frame per second (1fps).
*   Maintain this internal list of all kills *by `${username}`* throughout your analysis. This list is the *foundation* for Step 2. If no kills by `${username}` are found in the kill feed, proceed to output an empty list as per Step 2.

**STEP 2: Highlight Generation (Final JSON Output)**
Based *solely* on the comprehensive list of kills by `${username}` you identified in STEP 1 (derived *exclusively from the kill feed region*), generate the highlight clips.

**OUTPUT REQUIREMENTS:**
*   Output MUST be a JSON list of highlight objects.
*   If there are NO kills by `${username}` in the entire video (based on your STEP 1 analysis of the kill feed), output an empty list `[]`.
*   Each highlight object MUST contain:
    *   `"timestamp_start_seconds"`: number (integer, e.g., 55)
    *   `"timestamp_end_seconds"`: number (integer, e.g., 90)
    *   `"title"`: string (catchy, relevant title for the highlight clip)

**TITLE GENERATION REQUIREMENTS:**
*   Generate a catchy, engaging title for each highlight that reflects the actual content
*   Titles should be relevant to what happens in the specific highlight (kills, weapons, situations, etc.)
*   Use a casual, gaming-focused tone similar to these examples:
    * "ak spray triple kill"
    * "awp double headshot"
    * "clutch 1v3 situation"
    * "deagle one tap"
    * "through smoke kills"
    * "entry fragging spree"
    * "eco round ace"
    * "pistol round domination"
    * "retake success"
    * "site hold defense"
*   Include relevant details like:
    * Weapon used if identifiable from kill feed
    * Number of kills (e.g., "double", "triple", "quad")
    * Situation type (e.g., "clutch", "entry", "retake")
    * Notable mechanics if apparent
*   Keep titles concise (typically 3-6 words)
*   Use lowercase for a casual feel unless emphasizing something

**HIGHLIGHT IDENTIFICATION CRITERIA (Apply to the kill list from STEP 1):**

**A. CONTENT TO INCLUDE (ONLY these moments qualify as highlights):**
    1.  Every sequence of one or more kills made by `${username}` (from your STEP 1 list, appearing in the kill feed).
    2.  If multiple kills by `${username}` appear in the kill feed in rapid succession or as part of what appears to be a continuous action sequence (based on the timing of kill feed entries), group them into a single highlight clip.

**B. TIMESTAMPING RULES (CRITICAL - Apply to each generated highlight):**
    1.  All timestamps MUST be in total SECONDS (e.g., 90 for 1:30).
    2.  Use the kill timestamps (when the kill entry appeared in the kill feed) from your STEP 1 list as the basis.
    3.  Add exactly a **2-second buffer BEFORE** the timestamp of the *first kill entry by `${username}`* in a highlight sequence.
    4.  Add exactly a **2-second buffer AFTER** the timestamp of the *last kill entry by `${username}`* in a highlight sequence.
    5.  Each individual highlight segment (from start buffer to end buffer) MUST be at least `${min_highlight_duration_seconds}` seconds long.
        *   If a qualifying kill sequence (with buffers) is shorter than `${min_highlight_duration_seconds}`, it should generally not be included.
        *   Exception: If it's a single, impactful kill (e.g., an AWP shot) that, with buffers, *still* doesn't meet the duration, consider if it can be logically grouped with another nearby kill by `${username}` (if one exists within a reasonable timeframe, e.g., 5-10 seconds). If not, it should be omitted to maintain the minimum duration.
    6.  If multiple distinct highlight-worthy action sequences by `${username}` (based on your STEP 1 kill list from the kill feed) occur but are separated by significant periods where no kills by `${username}` appear in the kill feed (e.g., more than 10-15 seconds), create separate highlight entries for each.

**C. CONTENT TO EXCLUDE (DO NOT INCLUDE any of the following in the final highlight clips):**
    1.  Moments where `${username}` is eliminated (i.e., `${username}` appears as the `victim_name` in the kill feed).
    2.  Any information or events occurring *outside* the specified kill feed region. Your analysis is blind to the rest of the screen.
    3.  Round win/loss announcements, spectator UI, player deaths *not* involving `${username}` as the killer – unless these somehow manifest *within the kill feed data itself* in a way that is relevant (which is unlikely for these items). The primary trigger is always a kill *by `${username}`* in the feed.
    4.  Moment where `${username}` is not included in the kill within the kill feed.
                            
**D. CONTENT TO CUT OUT/SHORTEN FROM HIGHLIGHTS (Refine segment boundaries based on Kill Feed activity):**
    1.  Trim any excessive periods *within a highlight segment* where no new kill entries by `${username}` are appearing in the kill feed. The "action" is defined by the appearance of relevant kill feed entries.
    2.  The start and end of a highlight are strictly defined by the first/last kill *by `${username}`* in a sequence (plus buffers). Do not extend significantly beyond this unless another kill *by `${username}`* from your STEP 1 list justifies it.

**VERIFICATION STEP (Internal check before finalizing JSON output):**
For each potential highlight generated from your STEP 1 kill list:
1.  Confirm `${username}` is the one getting the kill(s) for all relevant entries in the kill feed (i.e., `${username}` is on the left/killer side of the entry).
2.  Verify the `timestamp_start_seconds` and `timestamp_end_seconds` adhere to all buffer rules (B.3, B.4) and the `min_highlight_duration_seconds` (B.5).
3.  Ensure no excluded content (C), *as determinable from the kill feed itself*, is present.
4.  Re-evaluate the segment: Is there an excessive time gap *between relevant kill feed entries by `${username}`* within the highlight? If so, consider if it should be split into multiple highlights (per rule B.6). Is there another kill by `${username}` (from your STEP 1 list) immediately before the start or after the end that should be included? Expand the timestamps to include it, respecting buffer and grouping rules.
5.  Generate an appropriate title that captures the essence of what happens in this specific highlight based on the kill feed data.

**MOTIVATION:**
Remember that this video will ABSOLUTELY have a highlight featuring `${username}` if they secured any kills. It's up to you to find it based *only* on the kill feed evidence. It's critical to ouput at least one highlight.

**EXAMPLE HIGHLIGHT FORMAT (Based on your STEP 1 analysis of the kill feed):**
```json
[
  {
    "timestamp_start_seconds": 35,
    "timestamp_end_seconds": 48,
    "title": "ak triple kill"
  },
  {
    "timestamp_start_seconds": 119,
    "timestamp_end_seconds": 130,
    "title": "awp double headshot"
  }
]
    ''') 