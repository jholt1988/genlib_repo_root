from __future__ import annotations

from textual.containers import Horizontal
from textual.widgets import Button, Input


class PromptBox(Horizontal):
    '''
    A dedicated prompt input + submit button.
    Emits `PromptBox.Submitted(prompt_text)` when submitted.
    '''

    class Submitted(Input.Submitted):
        pass

    def __init__(self, placeholder: str = "Describe what you want to generate...", **kwargs):
        super().__init__(**kwargs)
        self._placeholder = placeholder

    def compose(self):
        self.input = Input(placeholder=self._placeholder, id="agent-prompt-input")
        self.submit = Button("Plan", id="agent-prompt-submit")
        yield self.input
        yield self.submit

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "agent-prompt-submit":
            self.post_message(self.Submitted(self.input, value=self.input.value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "agent-prompt-input":
            self.post_message(self.Submitted(event.input, value=event.value))
