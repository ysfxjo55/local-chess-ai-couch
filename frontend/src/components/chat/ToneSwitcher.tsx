import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { TONE_OPTIONS, type Tone } from "@/lib/toneprompt";

export function ToneSwitcher({
  tone,
  onChange,
}: {
  tone: Tone;
  onChange: (tone: Tone) => void;
}) {
  return (
    <ToggleGroup
      type="single"
      size="sm"
      value={tone}
      onValueChange={(v) => v && onChange(v as Tone)}
      className="gap-1"
    >
      {TONE_OPTIONS.map((opt) => (
        <ToggleGroupItem
          key={opt.value}
          value={opt.value}
          className="h-7 rounded-md px-1.5 text-[11px] sm:px-2.5 sm:text-xs data-[state=on]:bg-amber data-[state=on]:text-obsidian"
        >
          {opt.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
