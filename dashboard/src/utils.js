/**
 * Convert a string to Title Case.
 * "data analyst" → "Data Analyst"
 */
export const toTitleCase = (str) =>
  str.replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.slice(1).toLowerCase())
