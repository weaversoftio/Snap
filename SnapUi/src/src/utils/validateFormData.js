export const validateFormData = (data, setState, currentErrors = {}) => {
  const keys = Object.keys(data);
  const currentErrorKeys = Object.keys(currentErrors);
  console.log("validateFormData", {data, currentErrors})
  const errors = {};
  keys.map((key, index) => {
    if (!data[key] || data[key].toString().trim() === "") {
      errors[key] = true
    }
    if (currentErrors[key] && typeof currentErrors[key] !== "boolean") {
      errors[key] = currentErrors[key]
    }
  })
    console.log("validateFormData", {errors})

  if (Object.keys(errors).length) {
    console.log("validateFormData", {errors})
    setState({ ...errors })
    return true
  }
  return false
}