// jsdom parses and styles but never lays out, so it ships no
// `Element.prototype.scrollIntoView` at all — calling it throws instead of
// no-opping. Components that keep an active row in view (SearchCombobox,
// CuttingResultOverview, CuttingResultSheets, OnboardingSpotlight, the cutting
// editor) call it from ordinary open/select paths, so without this stub a test
// that merely opens a dropdown dies on an unhandled rejection thrown far from
// whatever it was asserting.
//
// A no-op is the entire contract: with no layout there is no scroll position to
// assert, so scrolling correctness belongs to the manual pass, not to jsdom.
Element.prototype.scrollIntoView = function scrollIntoView() {}
