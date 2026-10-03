pub struct Id(pub String);

impl From<&str> for Id {
    fn from(value: &str) -> Self {
        Id(normalise(value))
    }
}

impl From<String> for Id {
    fn from(value: String) -> Self {
        Id(normalise(&value))
    }
}

pub struct Client {
    name: String,
}

pub trait Describe {
    fn describe(&self) -> String;
}

impl Client {
    pub fn new(name: &str) -> Client {
        Client { name: normalise(name) }
    }

    pub fn describe(&self) -> String {
        self.name.clone()
    }
}

impl Describe for Client {
    fn describe(&self) -> String {
        label(&self.name)
    }
}

fn normalise(name: &str) -> String {
    name.trim().to_string()
}

fn label(name: &str) -> String {
    format!("client {}", name)
}
