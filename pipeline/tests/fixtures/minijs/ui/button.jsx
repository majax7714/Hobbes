function Label(props) {
  return <span>{props.text}</span>;
}

export function Button() {
  return <Label text="ok" />;
}
