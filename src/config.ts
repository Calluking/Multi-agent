export const MECHANISM_NAMES = ["dependency", "codomain", "testing"] as const;

export type MechanismName = typeof MECHANISM_NAMES[number];
export type MechanismSwitches = Record<MechanismName, boolean>;

export const ALL_MECHANISMS: MechanismSwitches = {
  dependency: true,
  codomain: true,
  testing: true,
};

export function parseMechanismSwitches(value?: string): MechanismSwitches {
  if (value === undefined || value.trim() === "all") {
    return { ...ALL_MECHANISMS };
  }
  if (value.trim() === "" || value.trim() === "none") {
    return { dependency: false, codomain: false, testing: false };
  }
  const enabled = new Set(value.split(",").map((item) => item.trim()).filter(Boolean));
  const unknown = [...enabled].filter((item) => !MECHANISM_NAMES.includes(item as MechanismName));
  if (unknown.length > 0) throw new Error(`unknown memory mechanism: ${unknown.join(", ")}`);
  return {
    dependency: enabled.has("dependency"),
    codomain: enabled.has("codomain"),
    testing: enabled.has("testing"),
  };
}
