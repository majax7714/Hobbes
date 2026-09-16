/* extc2.c — the other unit: it defines what extc.c declared, and calls
   the `main` extc.c defines. Both keys are bare names, so both joins
   cross the two units. */

#ifdef __cplusplus
extern "C" {
#endif

int shared_entry(int v);
int main(void);

#ifdef __cplusplus
}
#endif

int shared_entry(int v) {
    return v + 1;
}

int call_main(void) {
    return main();
}
