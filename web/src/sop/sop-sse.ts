export interface ServerSentEvent {
  event: string;
  data: string;
  id: string;
}

/** Incremental SSE framing; transport chunks need not align with lines/events. */
export function createSseParser(onEvent: (event: ServerSentEvent) => void) {
  let line = "";
  let event = "";
  let id = "";
  let data: string[] = [];
  let skipLf = false;
  let firstCharacter = true;
  let frameLength = 0;
  const maxFrameLength = 8 * 1024 * 1024;

  const processLine = () => {
    if (line === "") {
      if (data.length > 0) {
        onEvent({ event: event || "message", data: data.join("\n"), id });
      }
      data = [];
      event = "";
      frameLength = 0;
    } else if (!line.startsWith(":")) {
      const colon = line.indexOf(":");
      const field = colon < 0 ? line : line.slice(0, colon);
      let value = colon < 0 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "data") data.push(value);
      else if (field === "event") event = value;
      else if (field === "id" && !value.includes("\0")) id = value;
    }
    line = "";
  };

  return {
    push(chunk: string) {
      for (const character of chunk) {
        if (firstCharacter) {
          firstCharacter = false;
          if (character === "\uFEFF") continue;
        }
        if (skipLf) {
          skipLf = false;
          if (character === "\n") continue;
        }
        frameLength += 1;
        if (frameLength > maxFrameLength) {
          throw new Error("SOP 实时事件超过大小限制，请重新连接任务。");
        }
        if (character === "\r") {
          processLine();
          skipLf = true;
        } else if (character === "\n") {
          processLine();
        } else {
          line += character;
        }
      }
    },
    finish() {
      // The SSE protocol dispatches only at a blank line. An incomplete frame
      // at EOF is discarded so the task owner can reconnect from a snapshot.
      line = "";
      data = [];
      event = "";
    },
  };
}
