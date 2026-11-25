const byId = (id) => document.getElementById(id);
function switchPanel(showRegister){
  byId("login-panel").classList.toggle("auth-hidden",showRegister);
  byId("register-panel").classList.toggle("auth-hidden",!showRegister);
}
byId("show-register").addEventListener("click",()=>switchPanel(true));
byId("show-login").addEventListener("click",()=>switchPanel(false));
async function sendAuth(url,payload,errorId){
  const box=byId(errorId);box.style.display="none";box.textContent="";
  try{
    const response=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const data=await response.json();
    if(!response.ok)throw new Error(data.detail||"Authentication failed.");
    window.location.href="/";
  }catch(error){box.textContent=error.message;box.style.display="block";}
}
byId("login-form").addEventListener("submit",e=>{
  e.preventDefault();
  sendAuth("/api/auth/login",{email:byId("login-email").value,password:byId("login-password").value},"login-error");
});
byId("register-form").addEventListener("submit",e=>{
  e.preventDefault();
  const password=byId("register-password").value;
  if(password!==byId("register-confirm").value){
    const box=byId("register-error");box.textContent="The passwords do not match.";box.style.display="block";return;
  }
  sendAuth("/api/auth/register",{name:byId("register-name").value,email:byId("register-email").value,password},"register-error");
});
