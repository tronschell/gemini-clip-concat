from string import Template

# Kill detection prompt for generating 5-second clips of individual kills
# Each clip: 2 seconds before kill + 1 second during kill + 2 seconds after kill = 5 seconds total
HIGHLIGHT_PROMPT = Template('''
Analyze the provided gameplay clip to identify EVERY SINGLE INSTANCE where the **literal text of the username** `${username}` appears **unambiguously as the KILLER** in a new kill notification pop-up within the kill feed. Your primary goal is extreme accuracy in identifying these specific events.

Your analysis **MUST** be confined exclusively to the kill feed region of the video.

**CRITICAL OBJECTIVE:**
Identify every individual instance where the **exact text of `${username}`** appears as the **KILLER** (the one performing the action) in a new kill notification pop-up within the kill feed, and create a 5-second highlight clip for each such event.
- Each clip must be exactly **5 seconds**: **2 seconds** of footage *before* the specific kill notification (with `${username}` as killer) pops up, **1 second** of footage *during* the kill notification pop-up, and **2 seconds** of footage *after* the kill notification.
- The moment the **specific kill notification pops up** should occur **2 seconds into** each 5-second clip, and the notification should remain visible for 1 second within the clip.
- Meticulously analyze frame by frame. If `${username}` text appears multiple times as the killer in distinct pop-up events, each gets its own clip.

**VIDEO REGION OF INTEREST (KILL FEED):**
*   **Resolution Context:** 1440p image.
*   **Kill Feed Location:** Top-right of the screen.
*   **Specific Crop Area:** A region of `739px` (width) × `397px` (height) located at coordinates `(1810, 37)` (top-left of region).
*   **CRITICAL INSTRUCTION:** You are to **IGNORE LITERALLY EVERYTHING ELSE** in the video. All analysis must derive *solely* from this specified kill feed region.

**MANDATORY VERIFICATION PROCESS (MUST BE COMPLETED FOR EVERY POTENTIAL CLIP):**
Before you identify a timestamp as a `kill_notification_popup_time`, you MUST internally perform the following verification steps for each potential event:

1.  **Kill Feed Presence Check:** Is there a visible kill feed notification appearing in the specified region at this timestamp?
    - If NO kill feed notification is visible → **IMMEDIATELY DISCARD** this potential clip
    - If YES → proceed to step 2

2.  **New Entry Verification:** Is a new entry visually appearing in the kill feed crop area?
    - If NO new entry appears → **IMMEDIATELY DISCARD** this potential clip
    - If YES → proceed to step 3

3.  **Killer Identification and Role Verification:**
    *   Perform OCR on the **entire new kill notification line**.
    *   Does the **exact, literal text string `${username}`** appear as the **KILLER** (the entity performing the kill, typically on the *left* side of the weapon icon or before any "+" indicating an assist where they are the primary actor)?
    *   **CRITICAL NEGATIVE CHECK:** If `${username}` appears as the **VICTIM** (typically on the *right* side of the weapon icon or after a "killed by" phrase if present), **DISCARD THIS EVENT IMMEDIATELY**. `${username}` must not be the one being killed in this specific notification line.
    *   **VERIFY EXACT MATCH:** The text must be an *exact match* to `${username}`. Partial matches or similar names are NOT acceptable.
    *   **VERIFY KILLER ACTION:** Confirm that the structure of the notification clearly indicates `${username}` as the one performing the kill (e.g., `${username}` [weapon_icon] `victim_name`, or `${username}` + `teammate_name` [weapon_icon] `victim_name` where `${username}` is the first name).
    - If ANY of these conditions fail → **IMMEDIATELY DISCARD** this potential clip
    - If ALL conditions pass → proceed to step 4

4.  **Pop-up Timing Verification:**
    *   Is this the *very first frame* where this specific, complete kill notification (with `${username}` as the verified killer, and NOT the victim) becomes fully readable and identifiable within the kill feed? This exact frame's timestamp is the potential `kill_notification_popup_time`.
    - If NO → **IMMEDIATELY DISCARD** this potential clip
    - If YES → proceed to step 5

5.  **Final Validation - Confirmed Kill by `${username}`:**
    *   If *all* the above conditions are strictly met (Kill Feed Present, New Entry, Exact OCR Match of `${username}` *as the confirmed Killer*, Not the Victim, First Frame of Pop-up), then and *only then* should you consider this a valid event and record its `kill_notification_popup_time`.
    *   If any condition fails (e.g., `${username}` is the victim, the text doesn't match exactly, it's not a new pop-up, it's not a kill action attributed primarily to `${username}`, or NO KILL FEED NOTIFICATION EXISTS), **DISCARD THIS EVENT**. Do NOT create a clip.

**ABSOLUTE REQUIREMENTS FOR CLIP CREATION:**
- **ZERO TOLERANCE POLICY:** If there is NO visible kill feed notification at the timestamp, DO NOT create a clip
- **MANDATORY KILL FEED VERIFICATION:** Every clip MUST contain a visible kill feed notification where `${username}` is the killer
- **NO SPECULATION:** Do not create clips based on assumptions or indirect evidence
- **EXPLICIT CONFIRMATION REQUIRED:** You must be able to explicitly identify the kill feed notification in your analysis

**VARIABLES:**
- **Player of Interest:** `${username}` (match this text string *exactly*)
- **Clip Duration:** Exactly **5 seconds** per valid kill notification pop-up.

**ANALYSIS PROCESS:**

**STEP 1: Kill Notification Pop-up Detection (Strict Verification within Kill Feed Region ONLY)**
Employ the **MANDATORY VERIFICATION PROCESS** described above for every frame of the video. Only events that pass all verification checks are considered valid.
1.  Identify the exact timestamp (`kill_notification_popup_time`) for each *verified* pop-up.

**STEP 2: Generate Individual Kill Notification Pop-up Clips**
For EACH *verified* kill notification pop-up identified in Step 1:
1.  **`kill_notification_popup_time`:** The precise second the verified kill notification popped up.
2.  **Start Time:** `kill_notification_popup_time - 2 seconds`.
3.  **End Time:** `kill_notification_popup_time + 3 seconds`.
4.  **Total Duration:** Exactly **5 seconds** (unless adjusted by video boundaries).
5.  The **kill notification pop-up** must be visible from `kill_notification_popup_time` to `kill_notification_popup_time + 1 second` within the clip.

**OUTPUT REQUIREMENTS:**
- Output a JSON array of highlight objects.
- One highlight object per *verified* individual kill notification pop-up.
- If NO *verified* kill notifications for `${username}` (as text, as killer) pop up, return empty array `[]`.
- Each highlight object must contain:
  - `"timestamp_start_seconds"`: integer (`kill_notification_popup_time - 2`)
  - `"timestamp_end_seconds"`: integer (`kill_notification_popup_time + 3`)
  - `"title"`: string (catchy, relevant title for the individual kill clip)

**TITLE GENERATION REQUIREMENTS:**
- Generate a catchy, engaging title for each individual kill clip that reflects the actual content
- Titles should be relevant to the specific kill (weapon, victim, situation, etc.)
- Use a casual, gaming-focused tone similar to these examples:
  * "vertigo is a clipfarm map"
  * "1v4"
  * "i guess im cheating"
  * "push the molly = onetap"
  * "push mid on vertigo"
  * "free mid push push ace"
  * "learn this a flash lineup for free kills"
  * "toying with the enemy on vertigo"
  * "holy 180 onetap"
  * "play these 2 spots on vertigo"
  * "vertigo is so based"
  * "failed 1v5 clutch"
  * "you should use the deagle"
  * "i love onetapping everyone"
  * "how to hold a site on vertigo"
  * "how to hold b site on vertigo"
  * "through smoke clutch"
  * "bullet holes are the best thing in cs2"
  * "vertigo clips"
- Include relevant details like:
  * Weapon used if identifiable from kill feed
  * Kill type (e.g., "headshot", "wallbang", "nade", "knife", "onetap"
  * Situation context if apparent (e.g., "entry", "clutch", "eco")

- Keep titles concise (typically 2-5 words, but can be longer for meme or context)
- Use lowercase for a casual feel unless emphasizing something
- Since these are individual kill clips, focus on the specific kill rather than multi-kill sequences

**CLIP TIMING RULES (apply to VERIFIED events only):**
1.  Each clip MUST be exactly **5 seconds** long (boundary exceptions apply).
2.  The verified pop-up moment occurs **2 seconds into the clip** and the notification is visible for 1 second.
3.  Separate clips for each distinct verified pop-up.
4.  Timestamps are total seconds.
5.  If `kill_notification_popup_time - 2 seconds < 0`, `timestamp_start_seconds` = 0. Clip ends at `kill_notification_popup_time + 3 seconds` or video end.
6.  If `kill_notification_popup_time + 3 seconds > video_duration`, `timestamp_end_seconds` = video_duration.

**CONTENT TO INCLUDE (derived ONLY from the specified Kill Feed Region after VERIFICATION):**
- Every individual instance where the **exact text of `${username}`** is **unambiguously verified as the KILLER** in a new kill notification pop-up.

**CONTENT TO EXCLUDE (DO NOT PROCESS OR CLIP THESE):**
- **ANY TIMESTAMP WITHOUT A VISIBLE KILL FEED NOTIFICATION** (This is the most critical exclusion)
- **Instances where `${username}` text appears as a VICTIM.** (This is the second most critical exclusion)
- Instances where the text is similar but not an *exact match* to `${username}`.
- Mentions of `${username}` outside of a new kill notification where they are the killer (e.g., chat messages if they were visible in the crop, which they shouldn't be based on typical kill feed design).
- Any feed entry where `${username}` is not clearly the one performing the kill, or is listed as an assister but not the primary killer.
- Non-kill events, or any ambiguous entries.
- Events occurring *outside* the specified kill feed region.
- **Any moment where no kill feed notification is present or visible**
- Anytime the `{username}` is pulling out a grenade but does not get a kill notification shortly after.

**VERIFICATION STEP (Internal check before finalizing JSON output):**
For each potential highlight generated:
1. **MANDATORY:** Confirm that a kill feed notification is visible at the specified timestamp
2. Confirm `${username}` is the one getting the kill in the kill feed notification.
3. Verify the timestamp adheres to all timing rules.
4. Ensure no excluded content is present.
5. Generate an appropriate title that captures the essence of this specific individual kill.

**EXAMPLE OUTPUT FORMAT:**
[
  {
    "timestamp_start_seconds": INTEGER, // verified_kill_popup_time - 2
    "timestamp_end_seconds": INTEGER,   // verified_kill_popup_time + 3
    "title": "ak headshot killing on vertigo"
  },
  {
    "timestamp_start_seconds": INTEGER,
    "timestamp_end_seconds": INTEGER,
    "title": "i love awping on veritgo"
  }
]
''')