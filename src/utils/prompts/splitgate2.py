from string import Template

# Kill detection prompt for generating 5-second clips of individual kills in Splitgate 2
# Each clip: 2 seconds before kill + 1 second during kill + 2 seconds after kill = 5 seconds total
HIGHLIGHT_PROMPT = Template('''
**LLM TASK: Precise Kill Feed Event Extraction for Splitgate 2 Highlight Generation**

**CORE DIRECTIVE:** Your *sole* function is to act as a highly specialized kill feed event detector for Splitgate 2. You are to analyze the provided gameplay video file with extreme precision to identify **EVERY SINGLE INSTANCE** where the **literal text of the username** `${username}` appears **unambiguously as the KILLER** in a **newly appearing kill notification pop-up** within the designated kill feed region. Your primary goal is absolute accuracy in identifying these specific events. **No other actions, events, or text mentions are relevant for clip creation, regardless of perceived gameplay importance, unless they are a direct kill notification by `${username}` as the killer.**

Your analysis **MUST** be confined exclusively to the kill feed region of the video specified below.

**CRITICAL OBJECTIVE: Isolate Confirmed Kills by `${username}` in Splitgate 2**
Identify every individual instance where the **exact text of `${username}`** appears as the **KILLER** (the one performing the action) in a new kill notification pop-up within the kill feed. For each such verified event, you will define the parameters for a 5-second highlight clip.

*   Each clip must be exactly **5 seconds**: **2 seconds** of footage *before* the specific kill notification (with `${username}` as killer) pops up, **1 second** of footage *during* which the kill notification pop-up is clearly visible, and **2 seconds** of footage *after* the kill notification.
*   The moment the **specific kill notification pops up** (the `kill_notification_popup_time`) should occur precisely **2 seconds into** each 5-second clip.
*   Meticulously analyze frame by frame. If the `${username}` text appears multiple times as the killer in *distinct and separate* pop-up events, each such event generates its own unique 5-second clip.

**VIDEO REGION OF INTEREST (KILL FEED):**
*   **Resolution Context:** The video is assumed to be 1440p for these coordinates.
*   **Kill Feed Location:** Top-right of the screen (typical for Splitgate 2).
*   **Specific Crop Area for Analysis:** A rectangular region of `739px` (width) × `397px` (height) located at coordinates `(1810, 37)` (top-left X, Y of the region).
*   **CRITICAL INSTRUCTION:** You are to **IGNORE LITERALLY EVERYTHING ELSE** in the video outside this specified crop area. All analysis and event triggers must derive *solely* from visual information within this kill feed region. Do not infer events from actions or sounds outside this region.

**MANDATORY VERIFICATION PROCESS (MUST BE COMPLETED FOR EVERY POTENTIAL CLIP):**
Before you identify a timestamp as a `kill_notification_popup_time`, you **MUST** internally perform and pass ALL the following verification steps for each potential event. Failure at any step means the event is **IMMEDIATELY DISCARDED**.
For your internal thinking only output a MAXIMUM of 5 words per thinking step.

1.  **Kill Feed Presence & Activity Check:** At the potential timestamp, is there a visible kill feed displaying notifications within the specified crop region?
    *   If NO kill feed notifications are visible at all → **DISCARD** this potential event.
    *   If YES → proceed to step 2.

2.  **New Entry Verification:** Is this the frame where a new kill notification entry *begins its appearance animation* or *becomes fully visible for the first time* within the kill feed crop area? This implies the entry was not present, or was in a different state (e.g., still animating in, faded) in the immediately preceding frames. The notification must be fresh.
    *   If NO new entry is visually appearing or completing its appearance → **DISCARD** this potential event.
    *   If YES → proceed to step 3.

3.  **Killer Identification and Role Verification (within the NEW entry):**
    *   Perform OCR on the **entire content of the new kill notification line** identified in step 2.
    *   Does the **exact, literal text string `${username}`** appear within this new notification?
    *   Crucially, is `${username}` identified as the **KILLER** (the entity performing the kill, typically on the *left* side of a weapon icon, or the first name listed if multiple names are involved in a kill, e.g., `${username}` + `teammate` [weapon] `victim`)?
    *   **CRITICAL NEGATIVE CHECK (VICTIM):** If `${username}` appears as the **VICTIM** (e.g., on the right side of a weapon icon, or in a context like "...killed `${username}`"), **DISCARD THIS EVENT IMMEDIATELY.** `${username}` must not be the one being killed in this specific notification line.
    *   **VERIFY EXACT TEXT MATCH:** The OCR'd text must be an *exact, case-sensitive (if applicable to the game's display) match* to `${username}`. Partial matches, misspellings, or similar names are **NOT** acceptable.
    *   **VERIFY KILLER ACTION:** Confirm the structure of the notification unambiguously indicates `${username}` as the primary actor performing the kill. If `${username}` is listed as an assister (e.g., after a `+` sign and not the first/primary name), **DISCARD THIS EVENT.**
    *   If ANY of these sub-conditions (exact match as killer, not victim, primary actor) fail → **DISCARD** this potential event.
    *   If ALL sub-conditions pass → proceed to step 4.

4.  **Pop-up Timing Verification (First Clear Frame):**
    *   Is this the *very first frame* where this specific, complete kill notification (now verified with `${username}` as the killer, and NOT the victim) becomes fully readable and identifiable within the kill feed? This exact frame's timestamp is the potential `kill_notification_popup_time`.
    *   If NO (e.g., it was already visible in a previous frame, or it's not yet fully clear) → **DISCARD** this potential event.
    *   If YES → proceed to step 5.

5.  **Final Validation - Confirmed Kill Event by `${username}`:**
    *   If *all* the above conditions (Kill Feed Active, New Entry, Exact OCR Match of `${username}` *as the confirmed Killer*, Not the Victim, Correct Killer Role, First Frame of Pop-up) are strictly met, then and *only then* should you consider this a valid event and record its `kill_notification_popup_time`.
    *   If any condition, at any step, has failed, **DISCARD THIS EVENT**. Do **NOT** create a clip.

**ABSOLUTE REQUIREMENTS FOR CLIP CREATION (ZERO TOLERANCE):**
*   **NO KILL FEED, NO CLIP:** If there is NO clearly visible, new kill feed notification pop-up (as defined above) where `${username}` is the killer at the `kill_notification_popup_time`, DO NOT create a clip. This is the paramount rule.
*   **VISIBLE NOTIFICATION IN CLIP:** The kill notification itself, confirming `${username}` as the killer, MUST be visible for the 1-second duration starting at `kill_notification_popup_time`.
*   **NO SPECULATION OR INFERENCE:** Do not create clips based on assumptions, general gameplay context, or indirect evidence. Only explicit, visual confirmation of the kill notification matters.
*   **IGNORE NON-CONFORMING EVENTS:** Events not meeting every single criterion in the Mandatory Verification Process must be ignored.

**VARIABLES:**
*   **Player of Interest:** `${username}` (match this text string *exactly* as it appears in Splitgate 2's kill feed)
*   **Clip Duration:** Exactly **5 seconds** per valid kill notification pop-up.

**ANALYSIS PROCESS:**

**STEP 1: Kill Notification Pop-up Detection (Strict Adherence to Verification)**
Scrutinize the video frame by frame, applying the **MANDATORY VERIFICATION PROCESS** to every potential kill feed entry within the specified kill feed region ONLY. Only events that pass all five verification checks are considered valid.
1.  Identify the exact timestamp (`kill_notification_popup_time`) for each *verified* pop-up.

**STEP 2: Generate Individual Kill Notification Pop-up Clips**
For EACH *verified* kill notification pop-up identified in Step 1:
1.  **`kill_notification_popup_time`:** The precise second the verified kill notification popped up.
2.  **Start Time:** `kill_notification_popup_time - 2 seconds`.
3.  **End Time:** `kill_notification_popup_time + 3 seconds`.
4.  **Total Duration:** Exactly **5 seconds** (unless adjusted by video boundaries, see Clip Timing Rules).
5.  The **kill notification pop-up** must be visible from `kill_notification_popup_time` to `kill_notification_popup_time + 1 second` within the clip.

**CONTENT TO INCLUDE (STRICTLY LIMITED TO):**
*   Every individual instance where the **exact text of `${username}`** is **unambiguously verified as the KILLER** in a new kill notification pop-up within the specified kill feed region, according to the Mandatory Verification Process.

**CONTENT TO EXCLUDE (CRITICAL - DO NOT PROCESS OR CLIP THESE):**
Adherence to these exclusions is paramount for accuracy. Failure to exclude these will result in an incorrect analysis.

*   **ANY TIMESTAMP/EVENT NOT PASSING THE MANDATORY VERIFICATION PROCESS.**
*   **MISSING KILL FEED NOTIFICATION:** Any timestamp where no relevant kill feed notification (as defined) is popping up.
*   **`${username}` AS VICTIM:** Any instance where `${username}` is the one killed.
*   **INCORRECT NAME MATCH:** Text similar to, but not an *exact match* of, `${username}`.
*   **NON-KILLER ROLE:** `${username}` mentioned as an assister but not the primary killer.
*   **OUTSIDE KILL FEED:** Mentions of `${username}` or any events outside the specified kill feed crop.
*   **AMBIGUOUS ENTRIES:** Unclear or non-standard kill feed entries where `${username}`'s role as the killer is not certain.
*   **NON-KILL EVENTS:** Deaths by environment (unless attributed to `${username}` in the feed), self-inflicted deaths by others, etc.
*   **ALL OTHER GAMEPLAY ACTIONS BY `${username}` THAT DO NOT RESULT IN A VERIFIED KILL NOTIFICATION:**
    *   This includes, but is not limited to: portal placement, portal traversal, aiming, shooting/missing shots, movement, reloading, strategizing, callouts.
    *   **Specifically, using abilities, utility (e.g., placing portals, using jetpack, deploying equipment), or equipment that does *NOT* result in an immediate, verifiable kill notification pop-up (within the kill feed region) where `${username}` is the killer, is to be COMPLETELY IGNORED as a trigger for clip creation.**
    *   For absolute clarity: if `${username}` places a portal or uses jetpack mobility, and no kill notification *for `${username}` as the killer* appears in the kill feed as a direct and immediate result identifiable via the Mandatory Verification Process, then the act of portal placement or jetpack usage (and the time around it) is **NOT** a target event and **MUST BE DISCARDED**.
    *   These other gameplay actions are only captured if they happen to fall within the 2-second pre-roll or 2-second post-roll of a *legitimately verified kill notification pop-up by `${username}`*. The actions themselves do *not* trigger clip creation.

**CLIP TIMING RULES (apply to VERIFIED events only):**
1.  Each clip MUST be exactly **5 seconds** long.
2.  The verified `kill_notification_popup_time` occurs **2 seconds into the clip**, and the notification is visible for at least 1 second from that point.
3.  Separate clips for each distinct verified pop-up. Do not merge sequential kills into one longer clip unless their 5-second windows naturally overlap due to rapid succession.
4.  Timestamps are total seconds from the beginning of the video.
5.  If `kill_notification_popup_time - 2 seconds < 0`, then `timestamp_start_seconds` must be `0`. The clip will still attempt to be 5 seconds, ending at `kill_notification_popup_time + 3 seconds` (or video end).
6.  If `kill_notification_popup_time + 3 seconds > video_duration_seconds`, then `timestamp_end_seconds` must be `video_duration_seconds`.

**OUTPUT REQUIREMENTS:**
*   Output a JSON array of highlight objects.
*   One highlight object per *verified* individual kill notification pop-up.
*   If NO *verified* kill notifications for `${username}` (as text, as killer, per all rules) pop up, return an empty array `[]`.
*   Each highlight object must contain:
    *   `"timestamp_start_seconds"`: integer (`kill_notification_popup_time - 2`, adjusted for video start)
    *   `"timestamp_end_seconds"`: integer (`kill_notification_popup_time + 3`, adjusted for video end)
    *   `"title"`: string (catchy, relevant title for the individual kill clip)

**TITLE GENERATION REQUIREMENTS:**
*   Generate a catchy, engaging title for each *individual kill clip* that reflects the actual content of that specific kill in Splitgate 2.
*   Titles should be relevant to the specific kill (e.g., weapon used if identifiable from the kill feed, portal-assisted kills, aerial eliminations, or general context).
*   Use a casual, gaming-focused tone. Examples:
    *   "portal peek elimination"
    *   "nice aerial railgun shot"
    *   "portal flank for the kill"
    *   "jetpack dodge and counter"
    *   "quick portal escape kill"
    *   "arena control with smg"
    *   "portal mind games work"
    *   "clean sniper pick"
*   Keep titles concise (typically 2-6 words). Use lowercase for a casual feel.
*   Since these are individual kill clips, focus on *that specific kill* and Splitgate 2's unique mechanics when relevant.

**FINAL SANITY CHECK BEFORE OUTPUTTING JSON:**
For *every single clip* you are about to include in the JSON output, perform this internal review:
1.  **Re-confirm Kill Feed Event:** Looking at the frame corresponding to `timestamp_start_seconds + 2 seconds`, is there an *unambiguous, new kill feed notification* in the specified region where the *exact text `${username}`* is the *killer* and *not the victim*?
2.  **Re-confirm Exclusivity:** Am I including this clip *solely* because of this verified kill feed event, and explicitly *not* because of any other perceived gameplay importance, player skill, or player action (like portal placement or jetpack usage) that did *not* directly result in this specific kill feed entry?
3.  **Re-confirm Timing:** Does the `kill_notification_popup_time` (start + 2s) correctly mark the first appearance of this notification, and is the clip 5 seconds long (respecting video boundaries)?

If the answer to any part of this re-confirmation is 'no', or if there is any doubt, **DISCARD THE CLIP.** Prioritize extreme accuracy and adherence to the "kill feed notification by `${username}` as killer" rule above all else.
''') 