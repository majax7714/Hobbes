// Nest controller: the fixture's TS route surface.
import { Controller, Get } from "@nestjs/common";
import { normalize } from "./util.js";

@Controller("items")
export class ItemsController {
  @Get(":id")
  findOne(id: string) {
    return { id: normalize(id) };
  }
}
