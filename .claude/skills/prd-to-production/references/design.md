# Mockups and visual contract

Start after the compact brief is approved and current. Use `sources.md` to locate the bundled OpenDesign design-brief and Impeccable new-work/craft-floor guidance; search headings and read only the applicable sections. Use selected critique sections for review. Do not load the long upstream manuals wholesale. They are readable sources, not assumed installed commands.

## Direction and content

Honor the user's references, branding, and real assets. For a new identity, make a considered recommendation based on users/tasks; alternatives should resolve real choices. Create a recognizable idea through typography, composition, density, spacing, material, color, and interaction. Stock SaaS shells, arbitrary gradients, repeated cards, decorative metrics, and generic icons should have a product reason. These are deliberate decisions, not blanket style bans.

Operational UI prioritizes task efficiency. Select fonts/assets that exist and can ship; record their sources, weights, fallbacks, and loading. Specify semantic colors with contrast, spacing scale, radii, borders, elevations, and purposeful motion with reduced-motion behavior. Use the same icons and assets in mockups and implementation.

**No decorative subtexts in the UI:** exclude subtitles under headings, card blurbs, filler greetings, redundant helper sentences, promotional copy, and explanatory captions. Retain field/control labels, real data, units, errors, accessible instructions, and required operational/legal content. Resolve conflicts rather than silently delete requirements. Put design rationale outside the product canvas.

## Generate images for the complete inventory

1. Write `design/spec.md`: direction; exact tokens; shell and component dimensions/anatomy; visible copy; assets; interaction states; breakpoints; screen-specific layout rules. Cross-reference screen and requirement IDs. It must support faithful implementation without guessing behavior from pixels. For stateful components, specify exact visible validation/duplicate/failure/retry copy, which client/server condition selects it, and pending/disabled appearance. Separate rendered text from accessible descriptions; both must remain meaningful, but need not be identical.
2. Make isolated HTML/CSS or project-native prototypes in `design/prototypes/`. Render PNGs in a browser with loaded fonts and deterministic content; use a concrete ready selector and suppress incidental animation. These are design prototypes, not the production app.
3. Capture every page/tab separately on desktop and mobile; defaults are 1440×1000 and 390×844 unless the brief specifies otherwise. Include full scrollable content, deliberate mobile reflow, and key dialogs/empty/loading/error/destructive states as extra images or state boards. Small screens must not merely shrink the desktop canvas.
4. If using image generation for concepts, follow the available image-generation skill/tool. Translate the chosen concept into a deterministic render/spec before build approval; concept imagery alone cannot establish exact text or geometry. If image/browser tooling is unavailable, establish capture tooling or report the blocker. Text wireframes cannot substitute for requested mockup images.
5. Inspect the images for hierarchy, spacing, alignment, overflow, realistic text lengths, states, contrast, and no-subtext compliance. Make `design/contact-sheet.png` plus `design/index.md` linking full images. The sheet aids navigation; individual images remain legible.

Create `design/screens.json`:

```json
{
  "revision": "v1",
  "screens": [
    {"id": "P-projects", "desktop": "design/images/projects-desktop.png", "mobile": "design/images/projects-mobile.png", "states": ["design/images/projects-empty.png"]}
  ]
}
```

All paths are relative to `.prd-to-production/`. Every inventory ID must appear once, with distinct images for its actual content. State arrays may be empty when the spec covers behavior without extra imagery. Record viewports for later matched captures.

Record agreed minimum control targets and focus/pressed treatments, not just font size and padding. A line-height calculation does not guarantee the rendered minimum, and a pressed transform can shrink a passing resting target. Approved styling must retain functional labels, focus, keyboard, validation and disabled semantics.

## Iterate and approve

Show the gallery and individual images. Apply feedback across affected screens, shared tokens, spec, and manifest. Iterate until the user explicitly approves the complete current set. Silence, praise of one screen, and a revision request are not whole-set approval. Record the real message only after it arrives. Approval covers the manifest, spec, and design files.

Preserve the approved set as a visual baseline. Implementation captures belong under `qa/`; do not overwrite approved mockups with actual screenshots to hide drift. Use matching environments for comparison and explicitly review any residual font-rendering variation. Material visual changes require reapproval; material brief changes return to its gate.

After both approvals, compare the first representative real component/vertical slice against this contract on desktop and mobile **before** reusing it across screens; follow the first-slice checkpoint in `build-verify.md`. Include real error and pending states, not only the default view. Inspect actual/approved pixels and readable component crops with measured geometry: a small full-frame difference can hide wrong copy, wrapping or disabled colors. Preserve the baseline and identify the code, compiled assets, design revision and capture environment used for each comparison.
